################ Project configuration ################

project_id             = "p-dev-gce-60pf"
main_region            = "us-central1"
developers_group_email = "gcu_latam_team_devs@endava.com"

################ APIs to enable ################

apis_to_enable = {
  "p-dev-gce-60pf" = [
    "drive.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com"
  ],
}

################ MCP-Server Service Account and IAM Roles ################

mcp_server_service_account_name = "drive-mcp-server"

# Due to authentication is handled by the OAuth token, we don't need any IAM roles for the service account
mcp_server_iam_project_roles = {}

################ Artifact Registry ################

artifact_registry_name = "mcp-servers"

################ Cloud Run ################

mcp_server_cloud_run_name      = "drive-mcp-server"
mcp_server_cloud_run_image_tag = "latest"
# mcp_server_cloud_run_region = "us-central1" # if not set, it will use the region set in the region variable

mcp_server_cloud_run_env = {
  "LOG_LEVEL" = "INFO"
}
