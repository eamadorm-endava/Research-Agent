variable "project_id" {
  description = "Project ID"
  type        = string
}

variable "main_region" {
  description = "Main region for the resources"
  type        = string
}

variable "apis_to_enable" {
  description = "List of APIs to enable in the project"
  type        = list(string)
}

variable "mcp_server_service_account_name" {
  description = "Service account name for the MCP server"
  type        = string
}

variable "mcp_server_iam_project_roles" {
  description = "List of IAM roles to grant to the service account"
  type        = list(string)
}

variable "artifact_registry_name" {
  description = "Artifact Registry name"
  type        = string
}

variable "mcp_server_cloud_run_name" {
  description = "Cloud Run name for the MCP server"
  type        = string
}

variable "mcp_server_cloud_run_image_tag" {
  description = "Docker image tag for the Cloud Run deployment"
  type        = string
}

variable "mcp_server_cloud_run_region" {
  description = "Cloud Run region for the MCP server. If not set, it will use the region set in the region variable"
  type        = string
  default     = ""
}

variable "mcp_server_cloud_run_env" {
  description = "Environment variables for the Cloud Run deployment"
  type        = map(string)
  default     = {}
}

variable "mcp_server_cloud_run_min_instances" {
  description = "Minimum number of instances for the Cloud Run deployment"
  type        = number
  default     = 0
}

variable "mcp_server_cloud_run_cpu" {
  description = "CPU limit for the Cloud Run deployment"
  type        = string
  default     = "1"
}

variable "mcp_server_cloud_run_memory" {
  description = "Memory limit for the Cloud Run deployment"
  type        = string
  default     = "512Mi"
}

variable "mcp_server_cloud_run_labels" {
  description = "Labels for the Cloud Run deployment"
  type        = map(string)
  default     = {}
}

