data "google_project" "project" {
  project_id = var.project_id
}

module "enable_apis" {
  source = "../base_modules/api-manager"
  project_services = {
    (var.project_id) = var.services_to_enable
  }
}
