# project_id and main_region are passed dynamically via -var in CI/CD

apis_to_enable = [
  "run.googleapis.com",
  "compute.googleapis.com",
  "iap.googleapis.com",
  "certificatemanager.googleapis.com"
]

ui_frontend_sa_name = "osiris-ui-frontend"

ui_frontend_iam_project_roles = [
  "roles/run.invoker",
  "roles/logging.logWriter"
]

artifact_registry_name          = "mcp-servers"
ui_frontend_service_name        = "ui-frontend"
ui_frontend_service_name_test   = "test-ui-frontend"
vpc_name                        = "mcp-agent-vpc"
ui_frontend_cloud_run_image_tag = "latest"


# -------------------------------------------------------------------------
# Domain Configuration
# -------------------------------------------------------------------------
# Update these with your actual domains
# Ensure you have A records pointing to the provisioned global IP address
domain_name      = "osiris.endava.app"
test_domain_name = "test.osiris.endava.app"

load_balancer_ip = "136.81.113.202"
iap_accessor     = "group:osiris_app_users@endava.com"
