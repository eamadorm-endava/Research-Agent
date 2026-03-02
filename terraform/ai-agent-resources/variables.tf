
variable "project_id" {
  description = "The ID of the project where the service account will be created."
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

#AI Agent service account and IAM roles
variable "ai_agent_service_account_name" {
  description = "The name of the service account (the part before the @)."
  type        = string
}

variable "ai_agent_iam_project_roles" {
  description = "Map of project IDs to a list of roles to be assigned to the service account."
  type        = map(list(string))
  default     = {}
}

#vertex-ai-search-agent service account and IAM roles
variable "vertex_ai_agent_iam_project_roles" {
  description = "Map of project IDs to a list of roles to be assigned to the service account."
  type        = map(list(string))
  default     = {}
}
