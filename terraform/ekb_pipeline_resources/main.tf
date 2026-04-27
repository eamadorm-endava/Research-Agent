data "google_project" "project" {
  project_id = var.project_id
}

################ APIs ################
module "enable_apis" {
  source           = "../base_modules/api-manager"
  project_services = var.apis_to_enable
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
    module.enable_apis
  ]
}
