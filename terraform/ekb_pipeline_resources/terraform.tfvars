################ Project configuration ################

project_id                  = "ag-core-dev-fdx7"
main_region                 = "us-central1"
developers_group_email      = "gcu_latam_team_devs@endava.com"
agent_service_account_email = "adk-agent@ag-core-dev-fdx7.iam.gserviceaccount.com"

################ APIs to enable ################

apis_to_enable = {
  "ag-core-dev-fdx7" = [
    "run.googleapis.com",
    "dlp.googleapis.com",
    "aiplatform.googleapis.com"
  ],
}

################ EKB Pipeline Service Account and IAM Roles ################

ekb_pipeline_service_account_name = "ekb-pipeline-sa"

ekb_pipeline_iam_project_roles = {
  "ag-core-dev-fdx7" = [
    "roles/dlp.admin",
    "roles/aiplatform.user",
    "roles/storage.admin",
    "roles/bigquery.admin",
    "roles/logging.logWriter"
  ]
}

################ Artifact Registry ################

artifact_registry_name = "mcp-servers"

################ Cloud Run ################

ekb_pipeline_cloud_run_name      = "ekb-pipeline"
ekb_pipeline_cloud_run_image_tag = "latest"

ekb_pipeline_cloud_run_env = {
  "LOG_LEVEL" = "INFO"
}
