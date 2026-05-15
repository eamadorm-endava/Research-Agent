main_region            = "us-central1"
artifact_registry_name = "mcp-servers"

services_to_enable = [
  "cloudresourcemanager.googleapis.com",
  "iam.googleapis.com",
  "storage.googleapis.com",
  "bigquery.googleapis.com",
  "artifactregistry.googleapis.com",
  "bigqueryconnection.googleapis.com",
  "aiplatform.googleapis.com"
]