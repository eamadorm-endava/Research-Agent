# project_id and main_region are passed dynamically via -var in CI/CD

apis_to_enable = [
  "firestore.googleapis.com", # To store the credentials
  "run.googleapis.com"        # All the other APIs like artifact registry, aiplatform, are defined in shared resources and in ai_agent_resources
]
ui_backend_sa_name = "osiris-ui-backend"
ui_backend_iam_project_roles = [
  "roles/aiplatform.user",
  "roles/compute.viewer", # Read the configured IAP backend IDs for JWT validation
  "roles/datastore.user",
  "roles/serviceusage.serviceUsageConsumer",
  "roles/iam.serviceAccountOpenIdTokenCreator",
  "roles/secretmanager.secretAccessor"
]
artifact_registry_name  = "mcp-servers"
ui_backend_service_name = "ui-backend"
ui_backend_cloud_run_labels = {
  "service"   = "ui-backend"
  "component" = "osiris-custom-ui"
}

ui_backend_cloud_run_env = {
  "PUBLIC_BASE_URL"              = "https://osiris.endava.app"
  "AGENT_RESOURCE_NAME"          = "projects/1051281656239/locations/us-central1/reasoningEngines/5233147857510334464" # OSIRIS production
  "FIRESTORE_DB_NAME"            = "osiris"
  "FIRESTORE_COLLECTION_NAME"    = "user_oauth_tokens"
  "GOOGLE_OAUTH_REDIRECT_URI"    = "https://osiris.endava.app/api/auth/google/callback"
  "MICROSOFT_OAUTH_TENANT_ID"    = "93f8f3d2-54f6-417d-9a37-10ff2952f228"
  "MICROSOFT_OAUTH_REDIRECT_URI" = "https://osiris.endava.app/api/auth/microsoft/callback"
  "ATLASSIAN_OAUTH_REDIRECT_URI" = "https://osiris.endava.app/api/auth/atlassian/callback"
}
