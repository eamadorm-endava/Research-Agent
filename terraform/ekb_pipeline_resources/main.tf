data "google_project" "project" {
  project_id = var.project_id
}

################ APIs ################
module "enable_apis" {
  source           = "../base_modules/api-manager"
  project_services = var.project_services
}

################ Service Accounts ################
module "ekb-pipeline-service-account" {
  source     = "../base_modules/iam-service-account"
  project_id = var.project_id
  name       = var.ekb_pipeline_service_account_name

  # authoritative roles granted *on* the service account
  iam = {
    "roles/iam.serviceAccountTokenCreator" = ["group:${var.developers_group_email}"]
  }

  # non-authoritative roles granted *to* the service account
  iam_project_roles = var.ekb_pipeline_iam_project_roles

  depends_on = [
    module.enable_apis
  ]
}

################ Cloud Run ################
locals {
  cloud_run_region = coalesce(var.ekb_pipeline_cloud_run_region, var.main_region)
  cloud_run_image  = "${local.cloud_run_region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_name}/${var.ekb_pipeline_cloud_run_name}"
}

module "ekb_pipeline_cloud_run" {
  source     = "../base_modules/cloud-run-v2"
  project_id = var.project_id
  region     = local.cloud_run_region
  name       = var.ekb_pipeline_cloud_run_name

  containers = {
    ekb-pipeline = {
      image = "${local.cloud_run_image}:${var.ekb_pipeline_cloud_run_image_tag}"
      env = merge(var.ekb_pipeline_cloud_run_env, {
        PROJECT_ID = var.project_id
      })
    }
  }

  service_config = {
    timeout = "3600s"
    scaling = {
      max_instance_count = 10
    }
  }

  # IAM for invocation (Authenticated only)
  iam = {
    "roles/run.invoker" = [
      "group:${var.developers_group_email}",
      "serviceAccount:${var.agent_service_account_email}"
    ]
  }

  service_account_config = {
    create = false
    email  = module.ekb-pipeline-service-account.email
  }

  depends_on = [
    module.enable_apis
  ]
}

################ BigQuery ML Model ################

resource "google_bigquery_connection" "vertex_ai_connection" {
  connection_id = "vertex_ai_connection"
  project       = var.project_id
  location      = var.main_region
  friendly_name = "Connection for Vertex AI embeddings"
  cloud_resource {}
}

resource "google_project_iam_member" "connection_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_bigquery_connection.vertex_ai_connection.cloud_resource[0].service_account_id}"
}

resource "google_bigquery_job" "create_multimodal_model" {
  job_id   = "create_model_${replace(timestamp(), "[: -]", "")}"
  project  = var.project_id
  location = var.main_region

  query {
    query          = <<EOF
      CREATE OR REPLACE MODEL `knowledge_base.multimodal_embedding_model`
      REMOTE WITH CONNECTION `${var.project_id}.${var.main_region}.${google_bigquery_connection.vertex_ai_connection.connection_id}`
      OPTIONS (ENDPOINT = 'multimodalembedding@001');
EOF
    use_legacy_sql = false
  }

  lifecycle {
    ignore_changes = [job_id]
  }

  depends_on = [
    google_bigquery_connection.vertex_ai_connection,
    google_project_iam_member.connection_ai_user,
    google_bigquery_table.documents_chunks,
    module.enable_apis
  ]
}

################ EKB Infrastructure (Migrated) ################

resource "google_bigquery_dataset" "knowledge_base" {
  dataset_id    = "knowledge_base"
  friendly_name = "knowledge_base"
  description   = "Enterprise Knowledge Base dataset"
  location      = var.main_region

  depends_on = [module.enable_apis]
}

resource "google_bigquery_table" "documents_chunks" {
  dataset_id = google_bigquery_dataset.knowledge_base.dataset_id
  table_id   = "documents_chunks"

  schema = <<EOF
[
  {
    "name": "chunk_id",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Unique UUID for the chunk"
  },
  {
    "name": "document_id",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Deterministic UUID for the document"
  },
  {
    "name": "chunk_data",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Text content of the chunk"
  },
  {
    "name": "gcs_uri",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Original GCS URI of the document"
  },
  {
    "name": "filename",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Basename of the file"
  },
  {
    "name": "structural_metadata",
    "type": "JSON",
    "mode": "REQUIRED",
    "description": "Structured page info, layout data, etc."
  },
  {
    "name": "page_number",
    "type": "INTEGER",
    "mode": "REQUIRED",
    "description": "Page number where the chunk was found"
  },
  {
    "name": "embedding",
    "type": "FLOAT64",
    "mode": "REPEATED",
    "description": "Vector embedding (empty initially)"
  },
  {
    "name": "created_at",
    "type": "TIMESTAMP",
    "mode": "REQUIRED",
    "description": "ISO timestamp of creation"
  },
  {
    "name": "vectorized_at",
    "type": "TIMESTAMP",
    "mode": "NULLABLE",
    "description": "ISO timestamp of vectorization"
  }
]
EOF
}

resource "google_bigquery_table" "documents_metadata" {
  dataset_id = google_bigquery_dataset.knowledge_base.dataset_id
  table_id   = "documents_metadata"

  schema = <<EOF
[
  {
    "name": "document_id",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Unique UUID for the document"
  },
  {
    "name": "gcs_uri",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Final GCS URI in the domain bucket (Original)"
  },
  {
    "name": "filename",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "The original filename"
  },
  {
    "name": "classification_tier",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "String classification label (public, confidential, etc.)"
  },
  {
    "name": "domain",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "The business domain (it, hr, etc.)"
  },
  {
    "name": "confidence_score",
    "type": "FLOAT64",
    "mode": "REQUIRED",
    "description": "AI classifier confidence (0.0 - 1.0)"
  },
  {
    "name": "trust_level",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Trust maturity (published, wip, archived)"
  },
  {
    "name": "project_id",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Project identifier"
  },
  {
    "name": "uploader_email",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Uploader's email address"
  },
  {
    "name": "description",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "AI-generated content summary"
  },
  {
    "name": "version",
    "type": "INTEGER",
    "mode": "REQUIRED",
    "description": "Incremental version number"
  },
  {
    "name": "latest",
    "type": "BOOLEAN",
    "mode": "REQUIRED",
    "description": "Whether this is the latest version"
  },
  {
    "name": "ingested_at",
    "type": "TIMESTAMP",
    "mode": "REQUIRED",
    "description": "ISO 8601 ingestion timestamp"
  }
]
EOF
}

resource "google_storage_bucket" "kb_landing_zone" {
  name          = "${var.project_id}-kb-landing-zone"
  location      = var.main_region
  force_destroy = true

  uniform_bucket_level_access = true
  depends_on                  = [module.enable_apis]
}

resource "google_storage_bucket" "rag_staging" {
  name          = "${var.project_id}-rag-staging"
  location      = var.main_region
  force_destroy = true

  uniform_bucket_level_access = true
  depends_on                  = [module.enable_apis]
}

locals {
  kb_domains = [
    "it",
    "finance",
    "hr",
    "sales",
    "executives",
    "legal",
    "operations"
  ]
}

resource "google_storage_bucket" "kb_domain_buckets" {
  for_each = toset(local.kb_domains)

  name          = "kb-${each.value}"
  location      = var.main_region
  force_destroy = true

  uniform_bucket_level_access = true
  depends_on                  = [module.enable_apis]
}

################ IAM (Resource Level) ################

# BQ Dataset Access
resource "google_bigquery_dataset_iam_member" "ekb_sa_bq_editor" {
  dataset_id = google_bigquery_dataset.knowledge_base.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${module.ekb-pipeline-service-account.email}"
}

# GCS Bucket Access (Landing Zone)
resource "google_storage_bucket_iam_member" "ekb_sa_landing_admin" {
  bucket = google_storage_bucket.kb_landing_zone.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.ekb-pipeline-service-account.email}"
}

# GCS Bucket Access (RAG Staging)
resource "google_storage_bucket_iam_member" "ekb_sa_rag_admin" {
  bucket = google_storage_bucket.rag_staging.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.ekb-pipeline-service-account.email}"
}

# GCS Bucket Access (Domain Buckets)
resource "google_storage_bucket_iam_member" "ekb_sa_domain_admin" {
  for_each = google_storage_bucket.kb_domain_buckets
  bucket   = each.value.name
  role     = "roles/storage.objectAdmin"
  member   = "serviceAccount:${module.ekb-pipeline-service-account.email}"
}
