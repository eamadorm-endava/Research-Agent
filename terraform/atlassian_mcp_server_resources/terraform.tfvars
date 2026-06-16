################ Project configuration ################

# project_id and main_region are passed dynamically via -var in CI/CD

################ APIs to enable ################

apis_to_enable = [
  "secretmanager.googleapis.com",
  "run.googleapis.com",
  "artifactregistry.googleapis.com"
]

################ MCP-Server Service Account and IAM Roles ################

mcp_server_service_account_name = "atlassian-mcp-server"

# Service roles are granted explicitly in main.tf (Storage & Secrets)
mcp_server_iam_project_roles = []

################ Artifact Registry ################

artifact_registry_name = "mcp-servers"

################ Cloud Run ################

mcp_server_cloud_run_name      = "atlassian-mcp-server"
mcp_server_cloud_run_image_tag = "latest"

mcp_server_cloud_run_env = {
  "LOG_LEVEL" = "INFO"
}

mcp_server_cloud_run_min_instances = 0
mcp_server_cloud_run_cpu           = "1"
mcp_server_cloud_run_memory        = "2Gi"
mcp_server_cloud_run_labels = {
  "service"   = "atlassian-mcp-server"
  "component" = "mcp-server"
}
