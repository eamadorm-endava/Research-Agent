output "backend_url" {
  description = "URL of the CloudRun Service containing the backend"
  value       = module.backend_cloud_run.service_uri
}

output "backend_service_account" {
  description = "Service account assigned to the Backend"
  value       = module.backend_sa.email
}
