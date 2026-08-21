# project_id and main_region are passed dynamically via -var in CI/CD

network_name           = "default"
subnetwork_name        = "default"
proxy_only_subnet_cidr = "10.129.0.0/23"
dns_zone_name          = "mcp-internal-zone"
dns_domain_name        = "mcp.internal."

mcp_services = [
  "bigquery-mcp-server",
  "calendar-mcp-server",
  "drive-mcp-server",
  "gcs-mcp-server",
  "onedrive-mcp-server",
  "outlook-mcp-server",
  "sharepoint-mcp-server",
  "atlassian-mcp-server",
  "ekb-pipeline"
]

apis_to_enable = [
  "compute.googleapis.com",
  "dns.googleapis.com",
  "servicenetworking.googleapis.com"
]
