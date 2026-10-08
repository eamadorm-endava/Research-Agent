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


data "google_project" "project" {
  project_id = var.project_id
}

resource "google_project_service_identity" "iap" {
  provider   = google-beta
  project    = var.project_id
  service    = "iap.googleapis.com"
  depends_on = [module.enable_apis]
}

locals {
  cloud_run_region = coalesce(var.ui_backend_cloud_run_region, var.main_region)
  cloud_run_image  = "${local.cloud_run_region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_name}/${var.ui_backend_service_name}"
  oauth_secrets = toset([
    "GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET",
    "MICROSOFT_OAUTH_CLIENT_ID", "MICROSOFT_OAUTH_CLIENT_SECRET",
    "ATLASSIAN_OAUTH_CLIENT_ID", "ATLASSIAN_OAUTH_CLIENT_SECRET"
  ])
  environments = {
    prod = { name = var.ui_backend_service_name, domain = var.domain_name, agent = var.agent_display_name }
    test = { name = "test-${var.ui_backend_service_name}", domain = var.test_domain_name, agent = var.test_agent_display_name }
  }
}

# Read only the backend service IDs used to validate signed IAP audiences.
resource "google_project_iam_custom_role" "iap_audience_reader" {
  project     = var.project_id
  role_id     = "osirisIapAudienceReader"
  title       = "OSIRIS IAP audience reader"
  permissions = ["compute.backendServices.get"]
}

resource "google_project_iam_member" "iap_audience_reader" {
  project = var.project_id
  role    = google_project_iam_custom_role.iap_audience_reader.name
  member  = "serviceAccount:${module.ui_backend_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "oauth" {
  for_each  = local.oauth_secrets
  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${module.ui_backend_sa.email}"
}

resource "google_storage_bucket_iam_member" "uploads" {
  bucket = "${var.project_id}-ai-agent-landing-zone"
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${module.ui_backend_sa.email}"
}

resource "google_service_account_iam_member" "upload_signer" {
  service_account_id = module.ui_backend_sa.id
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${module.ui_backend_sa.email}"
}

moved {
  from = module.ui_backend_cloud_run
  to   = module.ui_backend_cloud_run["prod"]
}

module "ui_backend_cloud_run" {
  for_each            = local.environments
  source              = "../base_modules/cloud-run-v2"
  project_id          = var.project_id
  region              = local.cloud_run_region
  name                = each.value.name
  labels              = var.ui_backend_cloud_run_labels
  deletion_protection = false
  revision            = { labels = var.ui_backend_cloud_run_labels }
  containers = {
    ui-backend = {
      image = "${local.cloud_run_image}:${var.ui_backend_cloud_run_image_tag}"
      env = merge(var.ui_backend_cloud_run_env, {
        PROJECT_ID                = var.project_id
        PROJECT_NUMBER            = data.google_project.project.number
        REGION                    = local.cloud_run_region
        ENVIRONMENT               = "production"
        AGENT_DISPLAY_NAME        = each.value.agent
        PUBLIC_BASE_URL           = "https://${each.value.domain}"
        ALLOWED_ORIGINS           = jsonencode(["https://${each.value.domain}"])
        IAP_BACKEND_SERVICES      = jsonencode(["ui-frontend-elb-${each.key}-backend", "ui-frontend-elb-${each.key}-api"])
        LANDING_ZONE_BUCKET       = "${var.project_id}-ai-agent-landing-zone"
        SERVICE_ACCOUNT_EMAIL     = module.ui_backend_sa.email
        FIRESTORE_DB_NAME         = "osiris"
        FIRESTORE_COLLECTION_NAME = each.key == "prod" ? "user_oauth_tokens" : "test_user_oauth_tokens"
      })
      env_from_key   = { for secret in local.oauth_secrets : secret => { secret = secret, version = "latest" } }
      resources      = { limits = { cpu = var.ui_backend_cloud_run_cpu, memory = var.ui_backend_cloud_run_memory } }
      startup_probe  = { http_get = { path = "/health", port = 8080 } }
      liveness_probe = { http_get = { path = "/health", port = 8080 } }
    }
  }
  iam = {
    "roles/run.invoker" = [
      "serviceAccount:${google_project_service_identity.iap.email}",
      "serviceAccount:${var.ui_frontend_sa_name}@${var.project_id}.iam.gserviceaccount.com"
    ]
  }
  service_account_config = { create = false, email = module.ui_backend_sa.email }
  service_config = {
    ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
    timeout = "300s"
    scaling = { min_instance_count = var.ui_backend_cloud_run_min_instances }
  }
  depends_on = [module.enable_apis, module.ui_backend_sa, google_secret_manager_secret_iam_member.oauth]
}

resource "google_firestore_field" "ephemeral_ttl" {
  for_each = toset([
    "user_oauth_tokens_oauth_states", "test_user_oauth_tokens_oauth_states",
    "user_oauth_tokens_refresh_locks", "test_user_oauth_tokens_refresh_locks"
  ])
  project    = var.project_id
  database   = "osiris"
  collection = each.value
  field      = "expires_at"
  ttl_config {}
}
