# project_id and main_region are passed dynamically via -var in CI/CD

apis_to_enable = [
  "firestore.googleapis.com", # To store the credentials
  "iap.googleapis.com",
  "compute.googleapis.com",
  "secretmanager.googleapis.com",
  "iamcredentials.googleapis.com",
  "storage.googleapis.com",
  "aiplatform.googleapis.com",
  "run.googleapis.com" # All the other APIs like artifact registry, aiplatform, are defined in shared resources and in ai_agent_resources
]
ui_backend_sa_name = "osiris-ui-backend"
ui_backend_iam_project_roles = [
  "roles/aiplatform.user",
  "roles/datastore.user",
  "roles/serviceusage.serviceUsageConsumer",
]
artifact_registry_name  = "mcp-servers"
ui_backend_service_name = "ui-backend"
ui_backend_cloud_run_labels = {
  "service"   = "ui-backend"
  "component" = "osiris-custom-ui"
}

domain_name             = "osiris.endava.app"
test_domain_name        = "test.osiris.endava.app"
agent_display_name      = "OSIRIS"
test_agent_display_name = "OSIRIS - Test"

ui_backend_cloud_run_env = {
  "MICROSOFT_OAUTH_TENANT_ID" = "93f8f3d2-54f6-417d-9a37-10ff2952f228"
}
