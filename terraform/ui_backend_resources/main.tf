module "enable_apis" {
  source           = "../base_modules/api-manager"
  project_services = { (var.project_id) = var.apis_to_enable }
}

module "ui_backend_sa" {
  source     = "../base_modules/iam-service-account"
  project_id = var.project_id
  name       = var.ui_backend_sa_name

  # Permission of the SA (non-authoritative roles granted to the service account)
  iam_project_roles = { (var.project_id) = var.ui_backend_iam_project_roles }

  depends_on = [
    module.enable_apis
  ]
}

################ Cloud Run ################
locals {
  cloud_run_region = coalesce(var.ui_backend_cloud_run_region, var.main_region)
  cloud_run_image  = "${local.cloud_run_region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_name}/${var.ui_backend_service_name}"
}

module "ui_backend_cloud_run" {
  source              = "../base_modules/cloud-run-v2"
  project_id          = var.project_id
  region              = local.cloud_run_region
  name                = var.ui_backend_service_name
  labels              = var.ui_backend_cloud_run_labels
  deletion_protection = false

  revision = {
    labels = var.ui_backend_cloud_run_labels
  }

  containers = {
    ui-backend = {
      image = "${local.cloud_run_image}:${var.ui_backend_cloud_run_image_tag}"
      env   = var.ui_backend_cloud_run_env
      env_from_key = {
        "GOOGLE_OAUTH_CLIENT_ID" = {
          secret  = "GOOGLE_OAUTH_CLIENT_ID"
          version = "latest"
        }
        "GOOGLE_OAUTH_CLIENT_SECRET" = {
          secret  = "GOOGLE_OAUTH_CLIENT_SECRET"
          version = "latest"
        }
        "MICROSOFT_OAUTH_CLIENT_ID" = {
          secret  = "MICROSOFT_OAUTH_CLIENT_ID"
          version = "latest"
        }
        "MICROSOFT_OAUTH_CLIENT_SECRET" = {
          secret  = "MICROSOFT_OAUTH_CLIENT_SECRET"
          version = "latest"
        }
        "ATLASSIAN_OAUTH_CLIENT_ID" = {
          secret  = "ATLASSIAN_OAUTH_CLIENT_ID"
          version = "latest"
        }
        "ATLASSIAN_OAUTH_CLIENT_SECRET" = {
          secret  = "ATLASSIAN_OAUTH_CLIENT_SECRET"
          version = "latest"
        }
      }
      resources = {
        limits = {
          cpu    = var.ui_backend_cloud_run_cpu
          memory = var.ui_backend_cloud_run_memory
        }
      }
    }
  }

  iam = {}

  service_account_config = {
    create = false
    email  = module.ui_backend_sa.email
  }

  service_config = {
    ingress = "INGRESS_TRAFFIC_INTERNAL_ONLY" # required to communicate with the frontend (frontend requires a VPC Egress)
    scaling = {
      min_instance_count = var.ui_backend_cloud_run_min_instances
    }
  }

  depends_on = [
    module.enable_apis,
    module.ui_backend_sa
  ]
}
