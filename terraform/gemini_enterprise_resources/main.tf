data "google_project" "project" {
  project_id = var.project_id
}

module "enable_apis" {
  source = "../base_modules/api-manager"
  project_services = {
    (var.project_id) = var.services_to_enable
  }
}

resource "google_project_service_identity" "discovery_engine_sa" {
  provider = google-beta
  project  = var.project_id
  service  = "discoveryengine.googleapis.com"

  depends_on = [module.enable_apis]
}

resource "google_project_iam_member" "discovery_engine_sa_roles" {
  for_each = toset(var.discovery_engine_service_agent_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_project_service_identity.discovery_engine_sa.email}"

  depends_on = [google_project_service_identity.discovery_engine_sa]
}
