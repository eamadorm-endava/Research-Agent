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
