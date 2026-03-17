output "mcp_server_service_account_email" {
  description = "Service account email used by the GCS MCP Cloud Run service."
  value       = module.mcp-server-service-account.email
}

output "cloud_run_service_name" {
  description = "GCS MCP Cloud Run service name."
  value       = module.mcp_server_cloud_run.service_name
}

output "cloud_run_service_url" {
  description = "GCS MCP Cloud Run public service URL."
  value       = module.mcp_server_cloud_run.service_uri
}
