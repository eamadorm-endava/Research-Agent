variable "project_id" {
  description = "The Google Cloud Project ID"
  type        = string
}

variable "main_region" {
  description = "The main GCP region for load balancer and serverless NEGs"
  type        = string
  default     = "us-central1"
}

variable "network_name" {
  description = "The VPC network where the Internal Load Balancer and Private DNS will be attached"
  type        = string
  default     = "mcp-agent-vpc"
}

variable "app_subnet_cidr" {
  description = "The CIDR range for the application subnet"
  type        = string
  default     = "10.10.0.0/24"
}

variable "proxy_only_subnet_cidr" {
  description = "The CIDR range for the Envoy proxy-only subnet (e.g. 10.129.0.0/23)"
  type        = string
  default     = "10.129.0.0/23"
}

variable "mcp_services" {
  description = "List of Cloud Run service names to attach to the Internal Load Balancer"
  type        = list(string)
  default = [
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
}

variable "dns_zone_name" {
  description = "Name of the Cloud DNS private managed zone"
  type        = string
  default     = "mcp-internal-zone"
}

variable "dns_domain_name" {
  description = "DNS domain name for the private zone"
  type        = string
  default     = "mcp.internal."
}

variable "apis_to_enable" {
  description = "List of Google Cloud APIs required for Load Balancing, Compute, and DNS"
  type        = list(string)
  default = [
    "compute.googleapis.com",
    "dns.googleapis.com",
    "servicenetworking.googleapis.com"
  ]
}
