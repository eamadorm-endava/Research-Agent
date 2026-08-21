variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "main_region" {
  description = "Primary region for resources"
  type        = string
  default     = "us-central1"
}

variable "services_to_enable" {
  description = "List of GCP APIs to enable for Gemini Enterprise"
  type        = list(string)
  default = [
    "discoveryengine.googleapis.com",
    "dialogflow.googleapis.com"
  ]
}

variable "sa_name" {
  description = "Terraform / Automation service account base name"
  type        = string
  default     = "terraform-sa-gemini-project"
}

variable "ge_sa_roles" {
  description = "IAM roles to grant to the service account for managing Gemini Enterprise"
  type        = list(string)
  default = [
    "roles/discoveryengine.admin",
    "roles/secretmanager.secretAccessor"
  ]
}
