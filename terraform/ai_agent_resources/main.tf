data "google_project" "project" {
  project_id = var.project_id
}


################ APIs ################
module "enable_apis" {
  source           = "../base_modules/api-manager"
  project_services = var.apis_to_enable
}


################ Service Accounts ################
resource "google_project_service_identity" "vertex_ai_sa" {
  provider = google-beta
  project  = var.project_id
  service  = "aiplatform.googleapis.com"
}

resource "google_project_service_identity" "discovery_engine_sa" {
  provider = google-beta
  project  = var.project_id
  service  = "discoveryengine.googleapis.com"
}

locals {
  vertex_ai_agent_email          = "serviceAccount:${google_project_service_identity.vertex_ai_sa.email}"
  discovery_engine_service_agent = "serviceAccount:${google_project_service_identity.discovery_engine_sa.email}"
}

module "ai-agent-service-account" {
  source     = "../base_modules/iam-service-account"
  project_id = var.project_id
  name       = var.ai_agent_service_account_name

  # authoritative roles granted *on* the service account
  # This SA can be impersonated by a user/group that needs to develop or test the ADK Agent capabilities.
  iam = {
    "roles/iam.serviceAccountTokenCreator" = ["group:${var.developers_group_email}"],
  }

  # non-authoritative roles granted *to* the service account
  iam_project_roles = var.ai_agent_iam_project_roles

  depends_on = [
    module.enable_apis
  ]
}


resource "google_project_iam_member" "vertex_ai_agent_roles" {
  for_each = toset(var.vertex_ai_agent_iam_project_roles[var.project_id])

  project = var.project_id
  role    = each.value
  member  = local.vertex_ai_agent_email

  depends_on = [
    module.enable_apis
  ]
}

resource "google_project_iam_member" "discovery_engine_service_agent_roles" {
  for_each = toset(var.discovery_engine_service_agent_iam_project_roles[var.project_id])

  project = var.project_id
  role    = each.value
  member  = local.discovery_engine_service_agent

  depends_on = [
    module.enable_apis
  ]
}

resource "google_storage_bucket_iam_member" "ai_agent_artifact_bucket_admin" {
  bucket = "${var.project_id}-${var.artifact_bucket_name}"
  role   = "roles/storage.admin"
  member = "serviceAccount:${module.ai-agent-service-account.email}"
}

################ Metrics ################
module "metrics_dataset" {
  source        = "../base_modules/bigquery-dataset"
  project_id    = var.project_id
  id            = var.bq_metrics_dataset_id
  location      = var.main_region
  friendly_name = var.bq_metrics_dataset_friendly_name
  description   = var.bq_metrics_dataset_description

  options = {
    delete_contents_on_destroy = true
  }

  tables = {
    (var.bq_metrics_table_id) = {
      friendly_name       = var.bq_metrics_table_friendly_name
      labels              = {}
      options             = null
      partitioning        = null
      deletion_protection = false
      schema = jsonencode([
        { name = "session_id", type = "STRING", mode = "REQUIRED", description = "Unique identifier for the session" },
        { name = "user_id", type = "STRING", mode = "NULLABLE", description = "Identifier for the user" },
        { name = "prompt_id", type = "STRING", mode = "REQUIRED", description = "Unique identifier for the prompt invocation" },
        { name = "prompt", type = "STRING", mode = "NULLABLE", description = "Text content of the user prompt" },
        { name = "agent_response", type = "STRING", mode = "NULLABLE", description = "Text content of the agent response" },
        { name = "initial_time", type = "TIMESTAMP", mode = "REQUIRED", description = "Timestamp when the prompt was received" },
        { name = "final_time", type = "TIMESTAMP", mode = "REQUIRED", description = "Timestamp when the response was returned" },
        { name = "time_to_answer", type = "FLOAT", mode = "REQUIRED", description = "Total processing time in seconds" },
        {
          name        = "tools_used",
          type        = "RECORD",
          mode        = "REPEATED",
          description = "List of tools invoked during the turn",
          fields = [
            { name = "tool_name", type = "STRING", mode = "REQUIRED", description = "Name of the tool executed" },
            { name = "initial_time", type = "TIMESTAMP", mode = "REQUIRED", description = "Timestamp when the tool started executing" },
            { name = "final_time", type = "TIMESTAMP", mode = "REQUIRED", description = "Timestamp when the tool completed executing" },
            { name = "tool_full_time", type = "FLOAT", mode = "REQUIRED", description = "Duration of tool execution in seconds" }
          ]
        }
      ])
    }
  }
}
