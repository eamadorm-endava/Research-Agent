
project_id             = "p-dev-gce-60pf"
developers_group_email = "gcu_latam_team_devs@endava.com"
apis_to_enable = {
  "p-dev-gce-60pf" = [
    "aiplatform.googleapis.com",
    "modelarmor.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudtrace.googleapis.com"
  ]
}
ai_agent_service_account_name = "adk-agent"
ai_agent_iam_project_roles = {
  "p-dev-gce-60pf" = [
    "roles/aiplatform.user",
    "roles/modelarmor.user",
    "roles/run.invoker",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/iam.serviceAccountOpenIdTokenCreator",
    "roles/cloudtrace.agent"
  ]
}
vertex_ai_agent_iam_project_roles = {
  "p-dev-gce-60pf" = [
    "roles/modelarmor.user",
    "roles/cloudtrace.agent"
  ]
}

discovery_engine_service_agent_iam_project_roles = {
  "p-dev-gce-60pf" = [
    "roles/aiplatform.user",
    "roles/modelarmor.user",
    "roles/discoveryengine.user",
    "roles/run.invoker"
  ]
}
