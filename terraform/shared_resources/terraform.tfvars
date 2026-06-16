# project_id and main_region are passed dynamically via -var in CI/CD
artifact_registry_name       = "mcp-servers"
ai_agent_landing_zone_bucket = "ai-agent-landing-zone"

services_to_enable = [
  "cloudresourcemanager.googleapis.com",
  "iam.googleapis.com",
  "storage.googleapis.com",
  "bigquery.googleapis.com",
  "artifactregistry.googleapis.com",
  "bigqueryconnection.googleapis.com",
  "aiplatform.googleapis.com"
]

################ Naming Configuration ################

bq_vertex_connection_id       = "vertex_ai_connection"
bq_dataset_id                 = "knowledge_base"
bq_chunks_table_id            = "documents_chunks"
bq_metadata_table_id          = "documents_metadata"
bq_jobs_table_id              = "ingestion_jobs"
kb_landing_zone_bucket_suffix = "-kb-landing-zone"
rag_staging_bucket_suffix     = "-rag-staging"
kb_domain_bucket_prefix       = "kb-"