variable "project_services" {
  description = "Service APIs to enable, mapped by project ID."
  type        = map(list(string))
  default     = {}
  # Example: 
  # { 
  #   "my-project-123" = ["compute.googleapis.com", "container.googleapis.com"] 
  # }
}

variable "disable_on_destroy" {
  description = "Whether to disable the service when the resource is destroyed."
  type        = bool
  default     = false
}

variable "disable_dependent_services" {
  description = "Whether to disable services that rely on the service being disabled."
  type        = bool
  default     = false
}