

variable "project_id" {
  description = "The ID of the project where the service account will be created."
  type        = string
}

variable "developers_group_email" {
  description = "The email of the Google Group that will be granted the Service Account User role."
  type        = string
}


#adk-agent service account and IAM roles

variable "adk-agent_service_account_name" {
  description = "The name of the service account (the part before the @)."
  type        = string
}


variable "adk-agent_iam_project_roles" {
  description = "Map of project IDs to a list of roles to be assigned to the service account."
  type        = map(list(string))
  default     = {}
}

#mcp-server service account and IAM roles

variable "mcp-server_service_account_name" {
  description = "The name of the service account (the part before the @)."
  type        = string
}

variable "mcp-server_iam_project_roles" {
  description = "Map of project IDs to a list of roles to be assigned to the service account."
  type        = map(list(string))
  default     = {}
}

#vertex-ai-search-agent service account and IAM roles

variable "vertex-ai-search-agent_iam_project_roles" {
  description = "Map of project IDs to a list of roles to be assigned to the service account."
  type        = map(list(string))
  default     = {}
}