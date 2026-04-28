variable "project_id" {
  description = "The ID of the project where shared resources are managed."
  type        = string
}

variable "main_region" {
  description = "Default region for shared resources."
  type        = string
}

variable "artifact_registry_name" {
  description = "The name of the shared Artifact Registry repository."
  type        = string
}

variable "artifact_registry_region" {
  description = "Optional override region for the shared Artifact Registry repository."
  type        = string
  default     = null
}

variable "project_services" {
  description = "Service APIs to enable, mapped by project ID."
  type        = map(list(string))
  default     = {}
}