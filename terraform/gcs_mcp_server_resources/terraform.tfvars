################ Project configuration ################

project_id             = "ag-core-dev-fdx7"
main_region            = "us-central1"
developers_group_email = "gcu_latam_team_devs@endava.com"

################ APIs to enable ################

apis_to_enable = {
  "ag-core-dev-fdx7" = [
    "storage.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com"
  ],
}

################ MCP-Server Service Account and IAM Roles ################

mcp_server_service_account_name = "gcs-mcp-server"

mcp_server_iam_project_roles = {
  "ag-core-dev-fdx7" = []
}

################ Artifact Registry ################

artifact_registry_name = "mcp-servers"

################ Cloud Run ################

mcp_server_cloud_run_name      = "gcs-mcp-server"
mcp_server_cloud_run_image_tag = "latest"
# mcp_server_cloud_run_region = "us-central1" # if not set, it will use the region set in the region variable

mcp_server_cloud_run_env = {
  "LOG_LEVEL"               = "INFO"
  "GCS_LANDING_ZONE_BUCKET" = "ai_agent_landing_zone"
  "GCS_KB_INGESTION_BUCKET" = "ag-core-dev-fdx7-kb-landing-zone"
}

landing_zone_bucket = "ai_agent_landing_zone"
kb_ingestion_bucket = "ag-core-dev-fdx7-kb-landing-zone"
