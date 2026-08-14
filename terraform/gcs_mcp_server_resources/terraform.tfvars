################ Project configuration ################

# The following are explicitly removed and MUST be passed via -var flags:
# project_id
# main_region
# landing_zone_bucket
# kb_ingestion_bucket

developers_group_email = "gcu_latam_team_devs@endava.com"

################ APIs to enable ################

apis_to_enable = [
  "storage.googleapis.com",
  "run.googleapis.com",
  "artifactregistry.googleapis.com"
]

################ MCP-Server Service Account and IAM Roles ################

mcp_server_service_account_name = "gcs-mcp-server"

mcp_server_iam_project_roles = []

################ Artifact Registry ################

artifact_registry_name = "mcp-servers"

################ Cloud Run ################

mcp_server_cloud_run_name      = "gcs-mcp-server"
mcp_server_cloud_run_image_tag = "latest"
# mcp_server_cloud_run_region = "us-central1" # if not set, it will use the region set in the region variable

mcp_server_cloud_run_env = {
  "LOG_LEVEL" = "INFO"
}

mcp_server_cloud_run_min_instances = 0
mcp_server_cloud_run_cpu           = "1"
mcp_server_cloud_run_memory        = "2Gi"
mcp_server_cloud_run_labels = {
  "service"   = "gcs-mcp-server"
  "component" = "mcp-server"
}
