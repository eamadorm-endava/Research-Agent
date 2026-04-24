terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.4.0"
    }
  }
}

# 1. Dedicated Service Account with exact least privilege roles
module "rag_sa" {
  source     = "github.com/terraform-google-modules/cloud-foundation-fabric//modules/iam-service-account?ref=v34.0.0"
  project_id = var.project_id
  name       = "rag-ingestion-sa"
  iam_project_roles = {
    "${var.project_id}" = [
      "roles/storage.objectViewer",
      "roles/bigquery.dataEditor",
      "roles/aiplatform.user",
      "roles/bigquery.connectionUser",
      "roles/dlp.jobsEditor"
    ]
  }
}

# 2. Cloud Function V2 utilizing CFF
module "rag_function" {
  source      = "github.com/terraform-google-modules/cloud-foundation-fabric//modules/cloud-function-v2?ref=v34.0.0"
  project_id  = var.project_id
  region      = var.region
  name        = "rag-ingestion-function"
  
  bucket_name = "${var.project_id}-rag-function-src"
  bucket_config = {
    location = var.region
  }

  bundle_config = {
    source_dir  = "${path.module}/../../"
    output_path = "${path.module}/rag-bundle.zip"
    excludes    = [".git", ".venv", "terraform", "notebooks", "docs"]
  }

  function_config = {
    entry_point = "rag_ingestion_http"
    runtime     = "python312"
  }

  service_config = {
    service_account_email = module.rag_sa.email
    available_memory      = "1024M"
    environment_variables = {
      PROJECT_ID = var.project_id
    }
  }

  # No allUsers invoker means it is not publicly accessible.
  iam = {}
}

# 3. BigQuery Cloud Resource Connection (if not exists)
resource "google_bigquery_connection" "vertex_ext" {
  project       = var.project_id
  connection_id = "vertex_ext_connection"
  location      = "US" # Usually multi-region for BigQuery
  cloud_resource {}
}
