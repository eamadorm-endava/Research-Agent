# project_id and main_region are passed dynamically via -var in CI/CD

developers_group_email = "gcu_latam_team_devs@endava.com"

apis_to_enable = [
  "aiplatform.googleapis.com",
  "modelarmor.googleapis.com",
  "cloudresourcemanager.googleapis.com",
  "cloudtrace.googleapis.com",
  "telemetry.googleapis.com",
  "logging.googleapis.com",
  "agentregistry.googleapis.com",
  "apphub.googleapis.com",
  "apptopology.googleapis.com",
  "connectors.googleapis.com",
  "iap.googleapis.com",
  "networksecurity.googleapis.com",
  "networkservices.googleapis.com",
  "notebooks.googleapis.com",
  "securitycenter.googleapis.com",
  "texttospeech.googleapis.com",
  "cloudapiregistry.googleapis.com",
  "observability.googleapis.com",
  "compute.googleapis.com",
  "dataform.googleapis.com",
  "iam.googleapis.com",
  "iamconnectors.googleapis.com",
  "monitoring.googleapis.com",
  "saasservicemgmt.googleapis.com",
  "storage.googleapis.com",
  "storage-component.googleapis.com"
]

ai_agent_service_account_name = "adk-agent"
landing_zone_bucket_name      = "ai-agent-landing-zone"
model_armor_template_id       = "security-template"

ai_agent_iam_project_roles = [
  "roles/aiplatform.user",
  "roles/modelarmor.user",
  "roles/run.invoker",
  "roles/serviceusage.serviceUsageConsumer",
  "roles/iam.serviceAccountOpenIdTokenCreator",
  "roles/cloudtrace.agent",
  "roles/agentregistry.admin",
  "roles/monitoring.metricWriter",
  "roles/logging.logWriter",
  "roles/telemetry.tracesWriter"
]

vertex_ai_agent_iam_project_roles = [
  "roles/modelarmor.user",
  "roles/cloudtrace.agent",
  "roles/monitoring.metricWriter",
  "roles/logging.logWriter"
]
