variable "project_id" {
  description = "The ID of the project where the service will be created."
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


variable "project_services" {
  description = "Service APIs to enable."
  type        = list(string)
  default     = []
}

# EKB Pipeline service account and IAM roles

variable "ekb_pipeline_service_account_name" {
  description = "The name of the service account (the part before the @)."
  type        = string
  default     = "ekb-pipeline-sa"
}

variable "ekb_pipeline_iam_project_roles" {
  description = "List of roles to be assigned to the service account."
  type        = list(string)
  default     = []
}

################ Artifact Registry ################

variable "artifact_registry_name" {
  description = "The name of the Artifact Registry repository."
  type        = string
}

################ Cloud Run ################

variable "ekb_pipeline_cloud_run_name" {
  description = "The name of the Cloud Run service."
  type        = string
  default     = "ekb-pipeline"
}

variable "ekb_pipeline_cloud_run_region" {
  description = "The region where the Cloud Run service will be deployed."
  type        = string
  default     = null
}

variable "ekb_pipeline_cloud_run_image_tag" {
  description = "The tag for the container image to deploy to Cloud Run."
  type        = string
  default     = "latest"
}

variable "ekb_pipeline_cloud_run_env" {
  description = "Environment variables for the Cloud Run container."
  type        = map(string)
  default     = {}
}

variable "ekb_pipeline_cloud_run_cpu" {
  description = "The number of vCPUs to allocate to the Cloud Run container."
  type        = string
  default     = "8"
}

variable "ekb_pipeline_cloud_run_memory" {
  description = "The amount of memory to allocate to the Cloud Run container."
  type        = string
  default     = "16Gi"
}

variable "ekb_pipeline_cloud_run_min_instances" {
  description = "The minimum number of instances to keep running for the Cloud Run service."
  type        = number
  default     = 0
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

