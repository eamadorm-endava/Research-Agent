################ Project configuration ################

project_id             = "ag-core-ops-auj0"
main_region            = "us-central1"
developers_group_email = "gcu_latam_team_devs@endava.com"

################ APIs to enable ################

apis_to_enable = {
  "ag-core-ops-auj0" = [
    "storage.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com"
  ],
}

################ MCP-Server Service Account and IAM Roles ################

mcp_server_service_account_name = "gcs-mcp-server"

mcp_server_iam_project_roles = {
  "ag-core-ops-auj0" = []
}

################ Artifact Registry ################

artifact_registry_name = "mcp-servers"

################ Cloud Run ################

mcp_server_cloud_run_name      = "gcs-mcp-server"
mcp_server_cloud_run_image_tag = "latest"
# mcp_server_cloud_run_region = "us-central1" # if not set, it will use the region set in the region variable

mcp_server_cloud_run_env = {
  "LOG_LEVEL"               = "INFO"
  "GCS_LANDING_ZONE_BUCKET" = "ag-core-ops-auj0-ai-agent-landing-zone"
  "GCS_KB_INGESTION_BUCKET" = "ag-core-ops-auj0-kb-landing-zone"
}

mcp_server_cloud_run_min_instances = 0
mcp_server_cloud_run_cpu           = "1"
mcp_server_cloud_run_memory        = "512Mi"
mcp_server_cloud_run_labels = {
  "service"   = "gcs-mcp-server"
  "component" = "mcp-server"
}

landing_zone_bucket = "ag-core-ops-auj0-ai-agent-landing-zone"
kb_ingestion_bucket = "ag-core-ops-auj0-kb-landing-zone"
