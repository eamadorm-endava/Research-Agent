variable "project_id" {
  description = "The ID of the project where the service account will be created."
  type        = string
}

variable "main_region" {
  description = "The main region of the project."
  type        = string
}

variable "developers_group_email" {
  description = "The email of the Google Group that will be granted the Service Account User role."
  type        = string
}

variable "apis_to_enable" {
  description = "Service APIs to enable, mapped by project ID."
  type        = map(list(string))
  default     = {}
}

#Drive mcp-server service account and IAM roles

variable "mcp_server_service_account_name" {
  description = "The name of the service account (the part before the @)."
  type        = string
}

variable "mcp_server_iam_project_roles" {
  description = "Map of project IDs to a list of roles to be assigned to the service account."
  type        = map(list(string))
  default     = {}
}

################ Artifact Registry ################

variable "artifact_registry_name" {
  description = "The name of the Artifact Registry repository."
  type        = string
}

################ Cloud Run ################

variable "mcp_server_cloud_run_name" {
  description = "The name of the Cloud Run service."
  type        = string
}

variable "mcp_server_cloud_run_region" {
  description = "The region where the Cloud Run service will be deployed."
  type        = string
  default     = null # Will default to var.region via coalescing in main.tf or explicitly passing
}

variable "mcp_server_cloud_run_image_tag" {
  description = "The tag for the container image to deploy to Cloud Run."
  type        = string
  default     = "latest"
}

variable "mcp_server_cloud_run_env" {
  description = "Environment variables for the Cloud Run container."
  type        = map(string)
  default     = {}
}
