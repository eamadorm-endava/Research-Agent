
variable "project_id" {
  description = "The ID of the project where the service account will be created."
  type        = string
}

variable "developers_group_email" {
  description = "The email of the Google Group that will be granted the Service Account User role."
  type        = string
}

variable "apis_to_enable" {
  description = "Service APIs to enable."
  type        = list(string)
  default     = []
}

variable "main_region" {
  description = "The main region for GCP resources."
  type        = string
}

variable "landing_zone_bucket_name" {
  description = "The name of the GCS bucket for session artifacts."
  type        = string
}

#AI Agent service account and IAM roles

variable "ai_agent_service_account_name" {
  description = "The name of the service account (the part before the @)."
  type        = string
}

variable "ai_agent_iam_project_roles" {
  description = "A list of roles to be assigned to the service account."
  type        = list(string)
  default     = []
}

#vertex-ai-search-agent service account and IAM roles
variable "vertex_ai_agent_iam_project_roles" {
  description = "A list of roles to be assigned to the service account."
  type        = list(string)
  default     = []
}

#Discovery Engine service account and IAM roles
variable "discovery_engine_service_agent_iam_project_roles" {
  description = "A list of roles to be assigned to the Discovery Engine service agent."
  type        = list(string)
  default     = []
}

variable "bq_metrics_dataset_id" {
  type        = string
  description = "The BigQuery dataset ID for metrics logging"
  default     = "agent_metrics"
}

variable "bq_metrics_dataset_description" {
  type        = string
  description = "The description for the BigQuery dataset"
  default     = "Dataset to collect agent and tool response time metrics"
}

variable "bq_metrics_table_id" {
  type        = string
  description = "The BigQuery table ID for response time metrics"
  default     = "response_times"
}
