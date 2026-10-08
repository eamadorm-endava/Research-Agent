variable "project_id" {
  description = "The ID of the project in which to provision resources."
  type        = string
}

variable "main_region" {
  description = "The main region to deploy resources."
  type        = string
}

variable "artifact_registry_name" {
  description = "The name of the Artifact Registry repository."
  type        = string
}

variable "vpc_name" {
  description = "Existing VPC used for Direct VPC egress."
  type        = string
  default     = "mcp-agent-vpc"
}


variable "ui_frontend_sa_name" {
  description = "The name of the service account for the UI frontend."
  type        = string
  default     = "osiris-ui-frontend"
}

variable "ui_frontend_service_name" {
  description = "The name of the prod Cloud Run service."
  type        = string
  default     = "ui-frontend"
}

variable "ui_frontend_service_name_test" {
  description = "The name of the test Cloud Run service."
  type        = string
  default     = "test-ui-frontend"
}

variable "ui_frontend_cloud_run_image_tag" {
  description = "The image tag for the prod Cloud Run service."
  type        = string
  default     = "latest"
}

variable "ui_frontend_cloud_run_cpu" {
  description = "The CPU limit for the UI frontend Cloud Run service."
  type        = string
  default     = "1"
}

variable "ui_frontend_cloud_run_memory" {
  description = "The memory limit for the UI frontend Cloud Run service."
  type        = string
  default     = "512Mi"
}

variable "ui_frontend_cloud_run_min_instances" {
  description = "The minimum number of instances for the UI frontend Cloud Run service."
  type        = number
  default     = 0
}

variable "apis_to_enable" {
  description = "List of APIs to enable for this deployment."
  type        = list(string)
}

variable "ui_frontend_iam_project_roles" {
  description = "List of roles to grant to the UI frontend Service Account."
  type        = list(string)
}


variable "domain_name" {
  description = "The custom domain name for the production frontend."
  type        = string
}

variable "test_domain_name" {
  description = "The custom domain name for the test frontend."
  type        = string
}

variable "iap_accessors" {
  description = "Users/groups allowed to access both UI environments through IAP."
  type        = set(string)
}

variable "load_balancer_ip" {
  description = "Reserved global IP to retain across UI deployments."
  type        = string
  default     = "136.81.113.202"
}
