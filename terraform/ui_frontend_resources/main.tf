module "enable_apis" {
  source           = "../base_modules/api-manager"
  project_services = { (var.project_id) = var.apis_to_enable }
}

data "google_project" "project" {
  project_id = var.project_id
}

module "ui_frontend_sa" {
  source     = "../base_modules/iam-service-account"
  project_id = var.project_id
  name       = var.ui_frontend_sa_name

  iam_project_roles = { (var.project_id) = var.ui_frontend_iam_project_roles }

  depends_on = [module.enable_apis]
}

data "google_secret_manager_secret_version" "iap_client_id" {
  secret  = "IAP_OSIRIS_CLIENT_ID"
  project = var.project_id
}

data "google_secret_manager_secret_version" "iap_client_secret" {
  secret  = "IAP_OSIRIS_CLIENT_SECRET"
  project = var.project_id
}

################ Cloud Run ################
locals {
  environments = {
    prod = { name = var.ui_frontend_service_name, domain = var.domain_name }
    test = { name = var.ui_frontend_service_name_test, domain = var.test_domain_name }
  }
  cloud_run_image = "${var.main_region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_name}/${var.ui_frontend_service_name}"
}

data "google_cloud_run_v2_service" "ui_backend" {
  for_each = local.environments
  name     = each.key == "prod" ? "ui-backend" : "test-ui-backend"
  location = var.main_region
  project  = var.project_id
}

moved {
  from = module.ui_frontend_cloud_run
  to   = module.ui_frontend_cloud_run["prod"]
}

module "ui_frontend_cloud_run" {
  for_each            = local.environments
  source              = "../base_modules/cloud-run-v2"
  project_id          = var.project_id
  region              = var.main_region
  name                = each.value.name
  deletion_protection = false

  revision = {
    session_affinity = true
    vpc_access = {
      network = var.vpc_name
      subnet  = "${var.vpc_name}-app-subnet-${var.main_region}"
      egress  = "ALL_TRAFFIC"
    }
  }

  containers = {
    ui-frontend = {
      image = "${local.cloud_run_image}:${var.ui_frontend_cloud_run_image_tag}"
      env = {
        API_URL         = "${data.google_cloud_run_v2_service.ui_backend[each.key].uri}/api"
        PUBLIC_BASE_URL = "https://${each.value.domain}"
      }
      resources = {
        limits = {
          cpu    = var.ui_frontend_cloud_run_cpu
          memory = var.ui_frontend_cloud_run_memory
        }
      }
    }
  }

  iam = {
    "roles/run.invoker" = [
      "serviceAccount:${data.google_service_account.iap.email}"
    ]
  }

  service_account_config = {
    create = false
    email  = module.ui_frontend_sa.email
  }

  service_config = {
    ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
    timeout = "3600s"
    scaling = {
      min_instance_count = var.ui_frontend_cloud_run_min_instances
    }
  }

  depends_on = [
    module.enable_apis,
    module.ui_frontend_sa
  ]
}

################ Serverless NEGs ################
resource "google_compute_region_network_endpoint_group" "prod_neg" {
  name                  = "neg-${var.ui_frontend_service_name}"
  network_endpoint_type = "SERVERLESS"
  region                = var.main_region
  project               = var.project_id

  cloud_run {
    service = module.ui_frontend_cloud_run["prod"].resource.name
  }

  depends_on = [module.enable_apis]
}

resource "google_compute_region_network_endpoint_group" "test_neg" {
  name                  = "neg-${var.ui_frontend_service_name_test}"
  network_endpoint_type = "SERVERLESS"
  region                = var.main_region
  project               = var.project_id

  cloud_run {
    service = module.ui_frontend_cloud_run["test"].resource.name
  }

  depends_on = [module.enable_apis]
}



################ Global IP and SSL Certificate ################
resource "google_compute_global_address" "ui_frontend_ip" {
  name    = "ui-frontend-global-ip"
  address = var.load_balancer_ip
  lifecycle { prevent_destroy = true }
  project = var.project_id
}

resource "google_compute_managed_ssl_certificate" "ui_frontend_cert" {
  name    = "ui-frontend-cert"
  project = var.project_id

  managed {
    domains = [var.domain_name, var.test_domain_name]
  }
}

################ External Load Balancer ################
module "ui_frontend_elb" {
  source     = "../base_modules/net-lb-app-ext"
  project_id = var.project_id
  name       = "ui-frontend-elb"

  protocol            = "HTTPS"
  use_classic_version = false

  forwarding_rules_config = {
    "" = {
      address = google_compute_global_address.ui_frontend_ip.address
    }
  }

  ssl_certificates = {
    certificate_ids = [google_compute_managed_ssl_certificate.ui_frontend_cert.self_link]
  }

  health_check_configs = {}
  backend_service_configs = merge({
    prod-backend = {
      health_checks = []
      iap_config = {
        enable               = true
        oauth2_client_id     = data.google_secret_manager_secret_version.iap_client_id.secret_data
        oauth2_client_secret = data.google_secret_manager_secret_version.iap_client_secret.secret_data
      }
      backends = [
        { backend = google_compute_region_network_endpoint_group.prod_neg.id }
      ]
    }
    test-backend = {
      health_checks = []
      iap_config = {
        enable               = true
        oauth2_client_id     = data.google_secret_manager_secret_version.iap_client_id.secret_data
        oauth2_client_secret = data.google_secret_manager_secret_version.iap_client_secret.secret_data
      }
      backends = [
        { backend = google_compute_region_network_endpoint_group.test_neg.id }
      ]
    }
    }, {
    for environment in keys(local.environments) : "${environment}-api" => {
      health_checks = []
      iap_config = {
        enable               = true
        oauth2_client_id     = data.google_secret_manager_secret_version.iap_client_id.secret_data
        oauth2_client_secret = data.google_secret_manager_secret_version.iap_client_secret.secret_data
      }
      backends = [{ backend = google_compute_region_network_endpoint_group.api_neg[environment].id }]
    }
  })

  urlmap_config = {
    default_service = "prod-backend"
    host_rules = [
      {
        hosts        = [var.test_domain_name]
        path_matcher = "test-paths"
      },
      {
        hosts        = [var.domain_name]
        path_matcher = "prod-paths"
      }
    ]
    path_matchers = {
      test-paths = {
        default_service = "test-backend"
        path_rules      = [{ paths = ["/api", "/api/*"], service = "test-api" }]
      }
      prod-paths = {
        default_service = "prod-backend"
        path_rules      = [{ paths = ["/api", "/api/*"], service = "prod-api" }]
      }
    }
  }
}

resource "google_compute_region_network_endpoint_group" "api_neg" {
  for_each              = local.environments
  name                  = "neg-${each.key}-ui-api"
  network_endpoint_type = "SERVERLESS"
  region                = var.main_region
  project               = var.project_id
  cloud_run { service = data.google_cloud_run_v2_service.ui_backend[each.key].name }
}

# IAP identity is owned by the backend stack; apply it first.
data "google_service_account" "iap" {
  project    = var.project_id
  account_id = "service-${data.google_project.project.number}@gcp-sa-iap.iam.gserviceaccount.com"
}

resource "google_iap_web_backend_service_iam_member" "users" {
  for_each            = { for pair in setproduct(["prod-backend", "test-backend", "prod-api", "test-api"], var.iap_accessors) : "${pair[0]}-${pair[1]}" => pair }
  project             = var.project_id
  web_backend_service = module.ui_frontend_elb.backend_service_names[each.value[0]]
  role                = "roles/iap.httpsResourceAccessor"
  member              = each.value[1]
}
