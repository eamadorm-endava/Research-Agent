data "google_project" "project" {
  project_id = var.project_id
}

locals {
  artifact_registry_region = coalesce(var.artifact_registry_region, var.main_region)
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
}

import {
  to = module.artifact_registry.google_artifact_registry_repository.registry
  id = "projects/${var.project_id}/locations/${local.artifact_registry_region}/repositories/${var.artifact_registry_name}"
}