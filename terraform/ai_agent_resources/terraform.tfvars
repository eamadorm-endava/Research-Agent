# project_id and main_region are passed dynamically via -var in CI/CD

developers_group_email = "gcu_latam_team_devs@endava.com"

apis_to_enable = [
  "aiplatform.googleapis.com",
  "modelarmor.googleapis.com",
  "cloudresourcemanager.googleapis.com",
  "cloudtrace.googleapis.com"
]

ai_agent_service_account_name = "adk-agent"
landing_zone_bucket_name      = "ai-agent-landing-zone"

ai_agent_iam_project_roles = [
  "roles/aiplatform.user",
  "roles/modelarmor.user",
  "roles/run.invoker",
  "roles/serviceusage.serviceUsageConsumer",
  "roles/iam.serviceAccountOpenIdTokenCreator",
  "roles/cloudtrace.agent"
]

vertex_ai_agent_iam_project_roles = [
  "roles/modelarmor.user",
  "roles/cloudtrace.agent"
]

discovery_engine_service_agent_iam_project_roles = [
  "roles/aiplatform.user",
  "roles/modelarmor.user",
  "roles/discoveryengine.user",
  "roles/run.invoker"
]

# Metrics Plugin
bq_metrics_dataset_id          = "agent_metrics"
bq_metrics_dataset_description = "Dataset to collect agent and tool response time metrics"
bq_metrics_table_id            = "response_times"
