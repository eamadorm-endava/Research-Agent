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

variable "services_to_enable" {
  description = "List of service APIs to enable in the project."
  type        = list(string)
  default     = []
}

variable "ai_agent_landing_zone_bucket" {
  description = "The name of the global AI Agent landing zone bucket."
  type        = string
}

variable "kb_domains" {
  description = "List of enterprise domains for knowledge base buckets."
  type        = list(string)
  default     = ["it", "finance", "hr", "sales", "executives", "legal", "operations"]
}

variable "bq_vertex_connection_id" {
  type = string
}

variable "bq_dataset_id" {
  type = string
}

variable "bq_chunks_table_id" {
  type = string
}

variable "bq_metadata_table_id" {
  type = string
}

variable "bq_jobs_table_id" {
  type = string
}

variable "kb_landing_zone_bucket_suffix" {
  type = string
}

variable "rag_staging_bucket_suffix" {
  type = string
}

variable "kb_domain_bucket_prefix" {
  type = string
}