################ Project configuration ################

project_id  = "ag-core-dev-fdx7"
main_region = "us-central1"

################ APIs to enable ################

apis_to_enable = {
  "ag-core-dev-fdx7" = [
    "calendar-json.googleapis.com",
    "meet.googleapis.com"
  ],
}

################ MCP-Server Service Account and IAM Roles ################

mcp_server_service_account_name = "calendar-mcp-server"

# Due to authentication is handled by the OAuth token, we don't need any IAM roles for the service account
mcp_server_iam_project_roles = {}

################ Artifact Registry ################

artifact_registry_name = "mcp-servers"

################ Cloud Run ################

mcp_server_cloud_run_name      = "calendar-mcp-server"
mcp_server_cloud_run_image_tag = "latest"
# mcp_server_cloud_run_region = "us-central1" # if not set, it will use the region set in the region variable

mcp_server_cloud_run_env = {
  "LOG_LEVEL" = "INFO"
}
