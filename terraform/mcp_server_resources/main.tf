data "google_project" "project" {
  project_id = var.project_id
}

################ APIs ################
module "enable_apis" {
  source           = "../base_modules/api-manager"
  project_services = var.apis_to_enable
}

################ Service Accounts ################
module "gemini-enterprise-project-mcp-server-service-account" {
  source     = "../base_modules/iam-service-account"
  project_id = var.project_id
  name       = var.mcp_server_service_account_name

  # authoritative roles granted *on* the service account
  iam = {
    "roles/iam.serviceAccountTokenCreator" = ["group:${var.developers_group_email}"]
  }

  # non-authoritative roles granted *to* the service account
  iam_project_roles = var.mcp_server_iam_project_roles

  depends_on = [
    module.enable_apis
  ]
}