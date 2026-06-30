data "google_project" "project" {
  project_id = var.project_id
}


################ APIs ################
module "enable_apis" {
  source           = "../base_modules/api-manager"
  project_services = { (var.project_id) = var.apis_to_enable }
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
  model_armor_location           = coalesce(var.model_armor_location, var.main_region)
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
  iam_project_roles = { (var.project_id) = var.ai_agent_iam_project_roles }

  depends_on = [
    module.enable_apis
  ]
}


resource "google_project_iam_member" "vertex_ai_agent_roles" {
  for_each = toset(var.vertex_ai_agent_iam_project_roles)

  project = var.project_id
  role    = each.value
  member  = local.vertex_ai_agent_email

  depends_on = [
    module.enable_apis
  ]
}

resource "google_project_iam_member" "discovery_engine_service_agent_roles" {
  for_each = toset(var.discovery_engine_service_agent_iam_project_roles)

  project = var.project_id
  role    = each.value
  member  = local.discovery_engine_service_agent

  depends_on = [
    module.enable_apis
  ]
}

resource "google_storage_bucket_iam_member" "ai_agent_landing_zone_bucket_admin" {
  bucket = "${var.project_id}-${var.landing_zone_bucket_name}"
  role   = "roles/storage.admin"
  member = "serviceAccount:${module.ai-agent-service-account.email}"
}

################ Model Armor Template ################
resource "google_model_armor_template" "security_template" {
  provider    = google-beta
  project     = var.project_id
  location    = local.model_armor_location
  template_id = var.model_armor_template_id

  template_metadata {
    log_template_operations = false
    log_sanitize_operations = false

    multi_language_detection {
      enable_multi_language_detection = true
    }
  }

  filter_config {
    malicious_uri_filter_settings {
      filter_enforcement = "ENABLED"
    }

    pi_and_jailbreak_filter_settings {
      filter_enforcement = "ENABLED"
    }

    rai_settings {
      rai_filters {
        filter_type      = "HATE_SPEECH"
        confidence_level = "HIGH"
      }
      rai_filters {
        filter_type      = "DANGEROUS"
        confidence_level = "HIGH"
      }
      rai_filters {
        filter_type      = "SEXUALLY_EXPLICIT"
        confidence_level = "HIGH"
      }
      rai_filters {
        filter_type      = "HARASSMENT"
        confidence_level = "HIGH"
      }
    }
  }

  depends_on = [
    module.enable_apis
  ]
}

################ Metrics ################
module "metrics_dataset" {
  source      = "../base_modules/bigquery-dataset"
  project_id  = var.project_id
  id          = var.bq_metrics_dataset_id
  location    = var.main_region
  description = var.bq_metrics_dataset_description

  options = {
    delete_contents_on_destroy = true
  }

  iam = {
    "roles/bigquery.dataEditor" = ["serviceAccount:${module.ai-agent-service-account.email}"]
  }

  tables = {
    (var.bq_metrics_table_id) = {
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
