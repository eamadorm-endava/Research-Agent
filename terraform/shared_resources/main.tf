data "google_project" "project" {
  project_id = var.project_id
}

locals {
  artifact_registry_region = coalesce(var.artifact_registry_region, var.main_region)
}

module "enable_apis" {
  source = "../base_modules/api-manager"
  project_services = {
    (var.project_id) = var.services_to_enable
  }
}

module "artifact_registry" {
  source     = "../base_modules/artifact-registry"
  project_id = var.project_id
  name       = var.artifact_registry_name
  location   = local.artifact_registry_region

  format = {
    docker = {
      standard = {}
    }
  }

  depends_on = [module.enable_apis]
} ################ BigQuery Data Foundation ################

resource "google_bigquery_connection" "vertex_ai_connection" {
  connection_id = var.bq_vertex_connection_id
  project       = var.project_id
  location      = var.main_region
  friendly_name = "Connection for Vertex AI embeddings"
  cloud_resource {}
  depends_on = [module.enable_apis]
}

resource "time_sleep" "wait_for_bq_connection_sa" {
  depends_on      = [google_bigquery_connection.vertex_ai_connection]
  create_duration = "30s"
}

resource "google_project_iam_member" "connection_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_bigquery_connection.vertex_ai_connection.cloud_resource[0].service_account_id}"

  depends_on = [time_sleep.wait_for_bq_connection_sa]
}

resource "google_bigquery_dataset" "knowledge_base" {
  project                    = var.project_id
  dataset_id                 = var.bq_dataset_id
  friendly_name              = "knowledge_base"
  description                = "Enterprise Knowledge Base dataset"
  location                   = var.main_region
  delete_contents_on_destroy = true
  depends_on                 = [module.enable_apis]
}

resource "google_bigquery_job" "create_multimodal_model" {
  # Deterministic job_id: stable within a project so re-applies don't re-run the job,
  # but changes when project_id or connection_id change (e.g. after a project migration),
  # which forces Terraform to destroy the stale state entry and create a fresh job.
  job_id   = "create-multimodal-model-${substr(md5("${var.project_id}-${var.bq_vertex_connection_id}"), 0, 8)}"
  project  = var.project_id
  location = var.main_region

  query {
    query              = <<EOF
      CREATE OR REPLACE MODEL `${var.bq_dataset_id}.multimodal_embedding_model`
      REMOTE WITH CONNECTION `${var.project_id}.${var.main_region}.${google_bigquery_connection.vertex_ai_connection.connection_id}`
      OPTIONS (ENDPOINT = 'multimodalembedding@001');
EOF
    use_legacy_sql     = false
    create_disposition = ""
    write_disposition  = ""
  }

  depends_on = [
    google_bigquery_connection.vertex_ai_connection,
    google_project_iam_member.connection_ai_user,
    google_bigquery_dataset.knowledge_base
  ]
}

resource "google_bigquery_table" "documents_chunks" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.knowledge_base.dataset_id
  table_id            = var.bq_chunks_table_id
  deletion_protection = false

  schema = <<EOF
[
  { "name": "chunk_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique UUID for the chunk" },
  { "name": "document_id", "type": "STRING", "mode": "REQUIRED", "description": "Deterministic UUID for the document" },
  { "name": "chunk_data", "type": "STRING", "mode": "REQUIRED", "description": "Text content of the chunk" },
  { "name": "gcs_uri", "type": "STRING", "mode": "REQUIRED", "description": "Original GCS URI of the document" },
  { "name": "filename", "type": "STRING", "mode": "REQUIRED", "description": "Basename of the file" },
  { "name": "structural_metadata", "type": "JSON", "mode": "REQUIRED", "description": "Structured page info, layout data, etc." },
  { "name": "page_number", "type": "INTEGER", "mode": "REQUIRED", "description": "Page number where the chunk was found" },
  { "name": "embedding", "type": "FLOAT64", "mode": "REPEATED", "description": "Vector embedding (empty initially)" },
  { "name": "created_at", "type": "TIMESTAMP", "mode": "REQUIRED", "description": "ISO timestamp of creation" },
  { "name": "vectorized_at", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "ISO timestamp of vectorization" }
]
EOF
}

resource "google_bigquery_table" "documents_metadata" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.knowledge_base.dataset_id
  table_id            = var.bq_metadata_table_id
  deletion_protection = false

  schema = <<EOF
[
  { "name": "document_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique UUID for the document" },
  { "name": "gcs_uri", "type": "STRING", "mode": "REQUIRED", "description": "Final GCS URI in the domain bucket (Original)" },
  { "name": "filename", "type": "STRING", "mode": "REQUIRED", "description": "The original filename" },
  { "name": "classification_tier", "type": "STRING", "mode": "REQUIRED", "description": "String classification label (public, confidential, etc.)" },
  { "name": "domain", "type": "STRING", "mode": "REQUIRED", "description": "The business domain (it, hr, etc.)" },
  { "name": "confidence_score", "type": "FLOAT64", "mode": "REQUIRED", "description": "AI classifier confidence (0.0 - 1.0)" },
  { "name": "trust_level", "type": "STRING", "mode": "REQUIRED", "description": "Trust maturity (published, wip, archived)" },
  { "name": "project_id", "type": "STRING", "mode": "REQUIRED", "description": "Project identifier" },
  { "name": "uploader_email", "type": "STRING", "mode": "REQUIRED", "description": "Uploader's email address" },
  { "name": "description", "type": "STRING", "mode": "REQUIRED", "description": "AI-generated content summary" },
  { "name": "version", "type": "INTEGER", "mode": "REQUIRED", "description": "Incremental version number" },
  { "name": "latest", "type": "BOOLEAN", "mode": "REQUIRED", "description": "Whether this is the latest version" },
  { "name": "ingested_at", "type": "TIMESTAMP", "mode": "REQUIRED", "description": "ISO 8601 ingestion timestamp" }
]
EOF
}

resource "google_bigquery_table" "ingestion_jobs" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.knowledge_base.dataset_id
  table_id            = var.bq_jobs_table_id
  deletion_protection = false

  schema = <<EOF
[
  { "name": "job_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique UUID for the ingestion job" },
  { "name": "filename", "type": "STRING", "mode": "REQUIRED", "description": "Basename of the file being ingested" },
  { "name": "status", "type": "STRING", "mode": "REQUIRED", "description": "Current status (processing, success, error)" },
  { "name": "message", "type": "STRING", "mode": "REQUIRED", "description": "Informational or error message" },
  { "name": "start_time", "type": "TIMESTAMP", "mode": "REQUIRED", "description": "When the job was initiated" },
  { "name": "end_time", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "When the job was finalized" },
  { "name": "metadata", "type": "STRING", "mode": "NULLABLE", "description": "Stringified JSON containing final processing results" }
]
EOF
}

################ Storage Data Foundation ################

resource "google_storage_bucket" "kb_landing_zone" {
  project                     = var.project_id
  name                        = "${var.project_id}${var.kb_landing_zone_bucket_suffix}"
  location                    = var.main_region
  force_destroy               = true
  uniform_bucket_level_access = true
  depends_on                  = [module.enable_apis]
}

resource "google_storage_bucket" "rag_staging" {
  project                     = var.project_id
  name                        = "${var.project_id}${var.rag_staging_bucket_suffix}"
  location                    = var.main_region
  force_destroy               = true
  uniform_bucket_level_access = true
  depends_on                  = [module.enable_apis]
}

resource "google_storage_bucket" "kb_domain_buckets" {
  for_each = toset(var.kb_domains)

  project                     = var.project_id
  name                        = "${var.project_id}-${var.kb_domain_bucket_prefix}${each.value}"
  location                    = var.main_region
  force_destroy               = true
  uniform_bucket_level_access = true
  depends_on                  = [module.enable_apis]
}

resource "google_storage_bucket" "landing_zone_bucket" {
  project                     = var.project_id
  name                        = "${var.project_id}-${var.ai_agent_landing_zone_bucket}"
  location                    = var.main_region
  uniform_bucket_level_access = true
  force_destroy               = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = var.landing_zone_retention_days
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [module.enable_apis]
}


