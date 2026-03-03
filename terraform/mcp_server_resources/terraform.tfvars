project_id             = "p-dev-gce-60pf"
developers_group_email = "research-agent-dev-test@endava.com"

apis_to_enable = {
  "p-dev-gce-60pf" = [
    "storage.googleapis.com",
    "drive.googleapis.com",
    "docs.googleapis.com",
    "bigquery.googleapis.com"
  ]
}

#mcp-server service account and IAM roles

mcp_server_service_account_name = "mcp-server"

mcp_server_iam_project_roles = {
  "p-dev-gce-60pf" = [
    "roles/storage.objectUser",
    "roles/bigquery.dataViewer",
    "roles/bigquery.jobUser"
  ]
}