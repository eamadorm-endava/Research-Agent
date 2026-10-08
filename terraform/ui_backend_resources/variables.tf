variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "main_region" {
  description = "GCP Region"
  type        = string
}

variable "apis_to_enable" {
  description = "List of the apis to enable to allow the backend to properly work"
  type        = list(string)
}


######################## Backend Service Account ########################
variable "ui_backend_sa_name" {
  description = "Name of the SA for the backend"
  type        = string
}

variable "ui_backend_iam_project_roles" {
  description = "List of IAM project roles for the backend service account"
  type        = list(string)
}


###################### Artifact Registry ###############################
variable "artifact_registry_name" {
  description = "The name of the Artifact Registry repository."
  type        = string
}

################### Cloud Run ####################
variable "ui_backend_service_name" {
  description = "Name of the service for the backend"
  type        = string
}

variable "ui_backend_cloud_run_region" {
  description = "Region of the Cloud Run service for the backend"
  type        = string
  default     = null # Will default to var.region via coalescing in main.tf or explicitly passing
}

variable "ui_backend_cloud_run_image_tag" {
  description = "The tag for the container image to deploy to Cloud Run"
  type        = string
  default     = "latest"
}

variable "ui_backend_cloud_run_env" {
  description = "Environment variables for the Cloud Run container"
  type        = map(string)
  default     = {}
}

variable "ui_backend_cloud_run_cpu" {
  description = "Number of vCPUs to allocate to the Cloud Run container"
  type        = string
  default     = "1"
}

variable "ui_backend_cloud_run_memory" {
  description = "The amount of memory to allocate to the Cloud Run container"
  type        = string
  default     = "512Mi"
}

variable "ui_backend_cloud_run_min_instances" {
  description = "Minimum number of instances to allocate to the Cloud Run container"
  type        = number
  default     = 0
}

variable "ui_backend_cloud_run_labels" {
  description = "A map of labels to apply to the Cloud Run service for billing revision"
  type        = map(string)
  default     = {}
}
