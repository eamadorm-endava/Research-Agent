project_id             = "ag-core-dev-fdx7"
main_region            = "us-central1"
artifact_registry_name = "mcp-servers"

project_services = {
  "ag-core-dev-fdx7" = [
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "artifactregistry.googleapis.com",
    "bigqueryconnection.googleapis.com",
    "aiplatform.googleapis.com"
  ]
}