project_id             = "ag-core-dev-fdx7"
main_region            = "us-central1"
artifact_registry_name = "mcp-servers"

apis_to_enable = {
  "ag-core-dev-fdx7" = [
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "artifactregistry.googleapis.com",
    "bigqueryconnection.googleapis.com",
    "aiplatform.googleapis.com"
  ]
}