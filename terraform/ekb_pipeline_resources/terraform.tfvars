################ Project configuration ################

# project_id and main_region are passed dynamically via -var in CI/CD

developers_group_email      = "gcu_latam_team_devs@endava.com"
agent_service_account_email = "adk-agent@ag-core-ops-auj0.iam.gserviceaccount.com"

################ APIs to enable ################

project_services = [
  "run.googleapis.com",
  "dlp.googleapis.com",
  "aiplatform.googleapis.com",
  "bigqueryconnection.googleapis.com",
  "cloudtasks.googleapis.com"
]

################ EKB Pipeline Service Account and IAM Roles ################

ekb_pipeline_service_account_name = "ekb-pipeline-sa"

ekb_pipeline_iam_project_roles = [
  "roles/dlp.admin",
  "roles/aiplatform.user",
  "roles/bigquery.jobUser",
  "roles/logging.logWriter"
]

################ Artifact Registry ################

artifact_registry_name = "mcp-servers"

################ Cloud Run ################

ekb_pipeline_cloud_run_name          = "ekb-pipeline"
ekb_pipeline_cloud_run_image_tag     = "latest"
ekb_pipeline_cloud_run_cpu           = "8"
ekb_pipeline_cloud_run_memory        = "32Gi"
ekb_pipeline_cloud_run_min_instances = 0

ekb_pipeline_cloud_run_env = {
  "LOG_LEVEL" = "INFO"
}

################ Naming Configuration for Shared Resources ################

bq_vertex_connection_id       = "vertex_ai_connection"
bq_dataset_id                 = "knowledge_base"
bq_chunks_table_id            = "documents_chunks"
bq_metadata_table_id          = "documents_metadata"
bq_jobs_table_id              = "ingestion_jobs"
kb_landing_zone_bucket_suffix = "-kb-landing-zone"
rag_staging_bucket_suffix     = "-rag-staging"
kb_domain_bucket_prefix       = "kb-"
