################ Project configuration ################

# project_id and main_region are passed dynamically via -var in CI/CD

developers_group_email = "gcu_latam_team_devs@endava.com"

################ APIs to enable ################

apis_to_enable = [
  "bigquery.googleapis.com",
  "run.googleapis.com",
  "artifactregistry.googleapis.com"
]

################ MCP-Server Service Account and IAM Roles ################

mcp_server_service_account_name = "bq-mcp-server"

mcp_server_iam_project_roles = []

################ Artifact Registry ################

artifact_registry_name = "mcp-servers"

################ Cloud Run ################

mcp_server_cloud_run_name      = "bigquery-mcp-server"
mcp_server_cloud_run_image_tag = "latest"
# mcp_server_cloud_run_region = "europe-west2" # if not set, it will use the region set in the region variable

mcp_server_cloud_run_env = {
  "LOG_LEVEL" = "INFO"
}

mcp_server_cloud_run_min_instances = 1
mcp_server_cloud_run_cpu           = "1"
mcp_server_cloud_run_memory        = "512Mi"
mcp_server_cloud_run_labels = {
  "service"   = "bq-mcp-server"
  "component" = "mcp-server"
}
