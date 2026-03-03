
project_id             = "p-dev-gce-60pf"
developers_group_email = "research-agent-dev-test@endava.com"
apis_to_enable = {
  "p-dev-gce-60pf" = [
    "aiplatform.googleapis.com",
    "modelarmor.googleapis.com",
  ]
}
ai_agent_service_account_name = "adk-agent"
ai_agent_iam_project_roles = {
  "p-dev-gce-60pf" = [
    "roles/aiplatform.user",
    "roles/modelarmor.user"
  ]
}
vertex_ai_agent_iam_project_roles = {
  "p-dev-gce-60pf" = [
    "roles/modelarmor.user"
  ]
}
