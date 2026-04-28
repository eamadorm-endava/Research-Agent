data "google_project" "project" {
  project_id = var.project_id
}

locals {
  artifact_registry_region = coalesce(var.artifact_registry_region, var.main_region)
}

module "enable_apis" {
  source           = "../base_modules/api-manager"
  project_services = var.project_services
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
}

resource "google_bigquery_dataset" "knowledge_base" {
  dataset_id    = "knowledge_base"
  friendly_name = "knowledge_base"
  description   = "Enterprise Knowledge Base dataset"
  location      = var.main_region
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
}


resource "google_storage_bucket" "rag_staging" {
  name          = "${var.project_id}-rag-staging"
  location      = var.main_region
  force_destroy = true

  uniform_bucket_level_access = true
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
}
