data "google_project" "project" {
  project_id = var.project_id
}

################ APIs ################
module "enable_apis" {
  source           = "../base_modules/api-manager"
  project_services = { (var.project_id) = var.apis_to_enable }
}

################ VPC Network & Subnets ################
resource "google_compute_network" "vpc" {
  name                    = var.network_name
  project                 = var.project_id
  auto_create_subnetworks = false

  depends_on = [module.enable_apis]
}

resource "google_compute_subnetwork" "app_subnet" {
  name          = "${var.network_name}-app-subnet-${var.main_region}"
  project       = var.project_id
  region        = var.main_region
  network       = google_compute_network.vpc.id
  ip_cidr_range = var.app_subnet_cidr
  purpose       = "PRIVATE"

  depends_on = [module.enable_apis]
}

################ Proxy-Only Subnet ################
# Regional Internal Application Load Balancers (Envoy-based L7) require a dedicated proxy-only subnet.
resource "google_compute_subnetwork" "proxy_only_subnet" {
  name          = "${var.network_name}-proxy-only-subnet-${var.main_region}"
  project       = var.project_id
  region        = var.main_region
  network       = google_compute_network.vpc.id
  ip_cidr_range = var.proxy_only_subnet_cidr
  purpose       = "REGIONAL_MANAGED_PROXY"
  role          = "ACTIVE"

  depends_on = [module.enable_apis]
}

################ Serverless Network Endpoint Groups (NEGs) ################
resource "google_compute_region_network_endpoint_group" "mcp_negs" {
  for_each              = toset(var.mcp_services)
  name                  = "${each.key}-neg"
  project               = var.project_id
  region                = var.main_region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = each.key
  }

  depends_on = [module.enable_apis]
}

################ Backend Services ################
resource "google_compute_region_backend_service" "mcp_backends" {
  for_each              = toset(var.mcp_services)
  name                  = "${each.key}-backend"
  project               = var.project_id
  region                = var.main_region
  protocol              = "HTTP"
  load_balancing_scheme = "INTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.mcp_negs[each.key].id
  }
}

################ URL Map & Path Matchers ################
resource "google_compute_region_url_map" "mcp_url_map" {
  name            = "mcp-gateway-url-map"
  project         = var.project_id
  region          = var.main_region
  default_service = google_compute_region_backend_service.mcp_backends["bigquery-mcp-server"].id

  # Host rule 1: Path routing via gateway.mcp.internal or any host
  host_rule {
    hosts        = ["*"]
    path_matcher = "all-mcp-paths"
  }

  path_matcher {
    name            = "all-mcp-paths"
    default_service = google_compute_region_backend_service.mcp_backends["bigquery-mcp-server"].id

    path_rule {
      paths   = ["/bq", "/bq/*"]
      service = google_compute_region_backend_service.mcp_backends["bigquery-mcp-server"].id
      route_action {
        url_rewrite {
          path_prefix_rewrite = "/"
        }
      }
    }

    path_rule {
      paths   = ["/calendar", "/calendar/*"]
      service = google_compute_region_backend_service.mcp_backends["calendar-mcp-server"].id
      route_action {
        url_rewrite {
          path_prefix_rewrite = "/"
        }
      }
    }

    path_rule {
      paths   = ["/drive", "/drive/*"]
      service = google_compute_region_backend_service.mcp_backends["drive-mcp-server"].id
      route_action {
        url_rewrite {
          path_prefix_rewrite = "/"
        }
      }
    }

    path_rule {
      paths   = ["/gcs", "/gcs/*"]
      service = google_compute_region_backend_service.mcp_backends["gcs-mcp-server"].id
      route_action {
        url_rewrite {
          path_prefix_rewrite = "/"
        }
      }
    }

    path_rule {
      paths   = ["/onedrive", "/onedrive/*"]
      service = google_compute_region_backend_service.mcp_backends["onedrive-mcp-server"].id
      route_action {
        url_rewrite {
          path_prefix_rewrite = "/"
        }
      }
    }

    path_rule {
      paths   = ["/outlook", "/outlook/*"]
      service = google_compute_region_backend_service.mcp_backends["outlook-mcp-server"].id
      route_action {
        url_rewrite {
          path_prefix_rewrite = "/"
        }
      }
    }

    path_rule {
      paths   = ["/sharepoint", "/sharepoint/*"]
      service = google_compute_region_backend_service.mcp_backends["sharepoint-mcp-server"].id
      route_action {
        url_rewrite {
          path_prefix_rewrite = "/"
        }
      }
    }

    path_rule {
      paths   = ["/atlassian", "/atlassian/*"]
      service = google_compute_region_backend_service.mcp_backends["atlassian-mcp-server"].id
      route_action {
        url_rewrite {
          path_prefix_rewrite = "/"
        }
      }
    }

    path_rule {
      paths   = ["/ekb", "/ekb/*"]
      service = google_compute_region_backend_service.mcp_backends["ekb-pipeline"].id
      route_action {
        url_rewrite {
          path_prefix_rewrite = "/"
        }
      }
    }
  }
}

################ Target HTTP Proxy ################
resource "google_compute_region_target_http_proxy" "mcp_target_proxy" {
  name    = "mcp-gateway-target-proxy"
  project = var.project_id
  region  = var.main_region
  url_map = google_compute_region_url_map.mcp_url_map.id
}

################ Internal Forwarding Rule ################
resource "google_compute_forwarding_rule" "mcp_forwarding_rule" {
  name                  = "mcp-gateway-forwarding-rule"
  project               = var.project_id
  region                = var.main_region
  ip_protocol           = "TCP"
  load_balancing_scheme = "INTERNAL_MANAGED"
  port_range            = "80"
  target                = google_compute_region_target_http_proxy.mcp_target_proxy.id
  network               = google_compute_network.vpc.id
  subnetwork            = google_compute_subnetwork.app_subnet.id

  depends_on = [
    google_compute_subnetwork.proxy_only_subnet
  ]
}

################ Cloud DNS Private Managed Zone ################
resource "google_dns_managed_zone" "mcp_private_zone" {
  name        = var.dns_zone_name
  dns_name    = var.dns_domain_name
  project     = var.project_id
  description = "Private DNS zone for MCP Services Gateway"
  visibility  = "private"

  private_visibility_config {
    networks {
      network_url = google_compute_network.vpc.id
    }
  }

  depends_on = [module.enable_apis]
}

resource "google_dns_record_set" "gateway_dns" {
  name         = "gateway.${var.dns_domain_name}"
  project      = var.project_id
  managed_zone = google_dns_managed_zone.mcp_private_zone.name
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_forwarding_rule.mcp_forwarding_rule.ip_address]
}

resource "google_dns_record_set" "wildcard_gateway_dns" {
  name         = "*.${var.dns_domain_name}"
  project      = var.project_id
  managed_zone = google_dns_managed_zone.mcp_private_zone.name
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_forwarding_rule.mcp_forwarding_rule.ip_address]
}

################ PSC Network Attachment for Vertex AI Agent Engine ################
resource "google_compute_network_attachment" "agent_network_attachment" {
  name                  = "${var.network_name}-network-attachment-${var.main_region}"
  project               = var.project_id
  region                = var.main_region
  subnetworks           = [google_compute_subnetwork.app_subnet.id]
  connection_preference = "ACCEPT_AUTOMATIC"

  depends_on = [google_compute_subnetwork.app_subnet]
}

# Grant Vertex AI Service Agent permissions for Network Attachment and DNS Peering
resource "google_project_iam_member" "vertex_network_admin" {
  project = var.project_id
  role    = "roles/compute.networkAdmin"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-aiplatform.iam.gserviceaccount.com"

  depends_on = [module.enable_apis]
}

resource "google_project_iam_member" "vertex_dns_peer" {
  project = var.project_id
  role    = "roles/dns.peer"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-aiplatform.iam.gserviceaccount.com"

  depends_on = [module.enable_apis]
}
