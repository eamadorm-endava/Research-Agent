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

variable "discovery_engine_service_agent_roles" {
  description = "A list of roles to be assigned to the Discovery Engine service agent."
  type        = list(string)
  default     = []
}
