variable "project_id" {
  description = "The ID of the project in which to provision resources."
  type        = string
}

variable "main_region" {
  description = "The main region to create the resources."
  type        = string
  default     = "europe-west1"
}

# ----------------- APIs Variable -----------------

variable "apis_to_enable" {
  type    = list(string)
  default = []
}

# ----------------- Service Account Variables -----------------

variable "mcp_server_service_account_name" {
  description = "The name of the service account for the MCP server."
  type        = string
}

variable "mcp_server_iam_project_roles" {
  description = "The IAM project roles to grant to the service account."
  type        = list(string)
  default     = []
}

# ----------------- Artifact Registry Variables -----------------

variable "artifact_registry_name" {
  description = "The name of the artifact registry."
  type        = string
}

# ----------------- Cloud Run Variables -----------------

variable "mcp_server_cloud_run_name" {
  description = "The name of the Cloud Run service."
  type        = string
}

variable "mcp_server_cloud_run_image_tag" {
  description = "The tag of the Docker image to deploy."
  type        = string
}

variable "mcp_server_cloud_run_region" {
  description = "The region of the Cloud Run service. Assumes main_region if not provided."
  type        = string
  default     = ""
}

variable "mcp_server_cloud_run_env" {
  description = "A map of environment variables to set on the Cloud Run service."
  type        = map(string)
  default     = {}
}

variable "mcp_server_cloud_run_min_instances" {
  description = "The minimum number of instances to keep running for the Cloud Run service."
  type        = number
  default     = 0
}

variable "mcp_server_cloud_run_cpu" {
  description = "The number of vCPUs to allocate to the Cloud Run container."
  type        = string
  default     = "1"
}

variable "mcp_server_cloud_run_memory" {
  description = "The amount of memory to allocate to the Cloud Run container."
  type        = string
  default     = "512Mi"
}

variable "mcp_server_cloud_run_labels" {
  description = "A map of labels to apply to the Cloud Run service and revision."
  type        = map(string)
  default     = {}
}

# ----------------- Storage / Landing Zone Bucket -----------------

variable "landing_zone_bucket" {
  description = "The name of the GCS bucket used as the landing zone."
  type        = string
}
