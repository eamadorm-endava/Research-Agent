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


