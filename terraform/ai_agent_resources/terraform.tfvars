
project_id             = "ag-core-dev-fdx7"
developers_group_email = "gcu_latam_team_devs@endava.com"
apis_to_enable = {
  "ag-core-dev-fdx7" = [
    "aiplatform.googleapis.com",
    "modelarmor.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudtrace.googleapis.com"
  ]
}
ai_agent_service_account_name = "adk-agent"
artifact_bucket_name          = "ai_agent_landing_zone"

ai_agent_iam_project_roles = {
  "ag-core-dev-fdx7" = [
    "roles/aiplatform.user",
    "roles/modelarmor.user",
    "roles/run.invoker",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/iam.serviceAccountOpenIdTokenCreator",
    "roles/cloudtrace.agent"
  ]
}
vertex_ai_agent_iam_project_roles = {
  "ag-core-dev-fdx7" = [
    "roles/modelarmor.user",
    "roles/cloudtrace.agent"
  ]
}

discovery_engine_service_agent_iam_project_roles = {
  "ag-core-dev-fdx7" = [
    "roles/aiplatform.user",
    "roles/modelarmor.user",
    "roles/discoveryengine.user",
    "roles/run.invoker"
  ]
}
