################ Project configuration ################

project_id             = "p-s-gcu-na-marketing-bd5y-1"
main_region            = "us-central1"
developers_group_email = "gcu_latam_team_devs@endava.com"

################ APIs to enable ################

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