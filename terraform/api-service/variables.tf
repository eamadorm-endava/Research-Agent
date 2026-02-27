variable "project_services" {
  description = "Service APIs to enable, mapped by project ID."
  type        = map(list(string))
  default     = {}
}