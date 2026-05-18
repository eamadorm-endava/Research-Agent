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
        PROJECT_ID            = var.project_id
        GEMINI_LOCATION       = var.main_region
        BQ_DATASET            = var.bq_dataset_id
        BQ_CHUNKS_TABLE       = var.bq_chunks_table_id
        BQ_METADATA_TABLE     = var.bq_metadata_table_id
        BQ_JOBS_TABLE         = var.bq_jobs_table_id
        RAG_STAGING_BUCKET    = "${var.project_id}${var.rag_staging_bucket_suffix}"
        TASKS_QUEUE_ID        = google_cloud_tasks_queue.ekb_ingestion_queue.name
        TASKS_LOCATION        = var.main_region
        SERVICE_ACCOUNT_EMAIL = module.ekb-pipeline-service-account.email
      })
      resources = {
        limits = {
          cpu    = var.ekb_pipeline_cloud_run_cpu
          memory = var.ekb_pipeline_cloud_run_memory
        }
      }
    }
  }

  service_config = {
    timeout = "3600s"
    scaling = {
      min_instance_count = var.ekb_pipeline_cloud_run_min_instances
      max_instance_count = 100
    }
  }

  # IAM for invocation (Authenticated only)
  iam = {
    "roles/run.invoker" = [
      "group:${var.developers_group_email}",
      "serviceAccount:${module.ekb-pipeline-service-account.email}"
    ]
  }

  service_account_config = {
    create = false
    email  = module.ekb-pipeline-service-account.email
  }

  deletion_protection = false

  depends_on = [
    module.enable_apis
  ]
}

################ Cloud Tasks ################

resource "google_cloud_tasks_queue" "ekb_ingestion_queue" {
  name     = "ekb-ingestion-queue"
  project  = var.project_id
  location = var.main_region

  rate_limits {
    max_concurrent_dispatches = 5
    max_dispatches_per_second = 2
  }

  retry_config {
    max_attempts = 1
    min_backoff  = "10s"
    max_backoff  = "300s"
  }
}

resource "google_project_iam_member" "cloudtasks_enqueuer" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${module.ekb-pipeline-service-account.email}"
}

resource "google_project_iam_member" "cloudtasks_oidc_creator" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${module.ekb-pipeline-service-account.email}"
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



################ IAM (Resource Level) ################

# BQ Dataset Access
resource "google_bigquery_dataset_iam_member" "ekb_sa_bq_editor" {
  project    = var.project_id
  dataset_id = var.bq_dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${module.ekb-pipeline-service-account.email}"
}

# BQ Connection Access (for ML.GENERATE_EMBEDDING)
resource "google_bigquery_connection_iam_member" "ekb_sa_connection_user" {
  project       = var.project_id
  location      = var.main_region
  connection_id = var.bq_vertex_connection_id
  role          = "roles/bigquery.connectionUser"
  member        = "serviceAccount:${module.ekb-pipeline-service-account.email}"
}

# GCS Bucket Access (Landing Zone)
resource "google_storage_bucket_iam_member" "ekb_sa_landing_admin" {
  bucket = "${var.project_id}${var.kb_landing_zone_bucket_suffix}"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.ekb-pipeline-service-account.email}"
}

# DLP API Service Agent access to Landing Zone (required to scan files during ingestion)
resource "google_storage_bucket_iam_member" "dlp_sa_landing_viewer" {
  bucket = "${var.project_id}${var.kb_landing_zone_bucket_suffix}"
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${data.google_project.project.number}@dlp-api.iam.gserviceaccount.com"
}

# GCS Bucket Access (RAG Staging)
resource "google_storage_bucket_iam_member" "ekb_sa_rag_admin" {
  bucket = "${var.project_id}${var.rag_staging_bucket_suffix}"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.ekb-pipeline-service-account.email}"
}

# GCS Bucket Access (Domain Buckets)
# roles/storage.admin is required (over objectAdmin) because the pipeline must call
# getIamPolicy/setIamPolicy on each domain bucket to grant uploaders conditional access
# to their own folder after routing.
resource "google_storage_bucket_iam_member" "ekb_sa_domain_admin" {
  for_each = toset(local.kb_domains)
  bucket   = "${var.project_id}-${var.kb_domain_bucket_prefix}${each.value}"
  role     = "roles/storage.admin"
  member   = "serviceAccount:${module.ekb-pipeline-service-account.email}"
}
