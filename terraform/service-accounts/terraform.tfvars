
project_id             = "p-dev-gce-60pf"
developers_group_email = "research-agent-dev-test@endava.com"


#adk-agent service account and IAM roles
adk-agent_service_account_name = "adk-agent"


adk-agent_iam_project_roles = {
  "p-dev-gce-60pf" = [
    "roles/aiplatform.user",
    "roles/modelarmor.user"
  ]
}

#mcp-server service account and IAM roles

mcp-server_service_account_name = "mcp-server"

mcp-server_iam_project_roles = {
  "p-dev-gce-60pf" = [
    "roles/storage.objectUser",
    "roles/bigquery.dataViewer",
    "roles/bigquery.jobUser"
  ]
}

#vertex-ai-service-agent service account and IAM roles
vertex-ai-search-agent_iam_project_roles = {
  "p-dev-gce-60pf" = [
    "roles/modelarmor.user"
  ]
}