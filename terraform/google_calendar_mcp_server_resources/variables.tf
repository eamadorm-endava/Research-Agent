variable "project_id" {
  description = "The ID of the project in which to provision resources."
  type        = string
}

variable "main_region" {
  description = "The main region to create the resources."
  type        = string
  default     = "us-central1"
}

# ----------------- APIs Variable -----------------

variable "apis_to_enable" {
  description = "A map of project IDs to lists of APIs to enable. Enables standard Google Cloud APIs required for core GCP services."
  type        = map(list(string))
  default     = {}
}

# ----------------- Service Account Variables -----------------

variable "mcp_server_service_account_name" {
  description = "The name of the service account for the MCP server."
  type        = string
}

variable "mcp_server_iam_project_roles" {
  description = "The IAM project roles to grant to the service account."
  type        = map(list(string))
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
