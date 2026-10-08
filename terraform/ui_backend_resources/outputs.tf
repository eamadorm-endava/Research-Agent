output "ui_backend_url" {
  description = "URL of the CloudRun Service containing the backend"
  value       = module.ui_backend_cloud_run["prod"].service_uri
}

output "ui_backend_service_account" {
  description = "Service account assigned to the Backend"
  value       = module.ui_backend_sa.email
}

output "test_ui_backend_url" {
  value = module.ui_backend_cloud_run["test"].service_uri
}
