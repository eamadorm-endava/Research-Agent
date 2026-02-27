data "google_project" "project" {
  project_id = var.project_id
}

locals {
  vertex_ai_agent_email = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-aiplatform.iam.gserviceaccount.com"
}

module "gemini-enterprise-project-adk-agent-service-account" {
  source     = "../modules/iam-service-account"
  project_id = var.project_id
  name       = var.adk-agent_service_account_name

  # authoritative roles granted *on* the service account
  iam = {
    "roles/iam.serviceAccountTokenCreator" = ["group:${var.developers_group_email}"],
  }

  # non-authoritative roles granted *to* the service account
  iam_project_roles = var.adk-agent_iam_project_roles
}

module "gemini-enterprise-project-mcp-server-service-account" {
  source     = "../modules/iam-service-account"
  project_id = var.project_id
  name       = var.mcp-server_service_account_name

  # authoritative roles granted *on* the service account
  iam = {
    "roles/iam.serviceAccountTokenCreator" = ["group:${var.developers_group_email}"]
  }

  # non-authoritative roles granted *to* the service account
  iam_project_roles = var.mcp-server_iam_project_roles
}

resource "google_project_iam_member" "vertex_ai_agent_roles" {
  for_each = toset(var.vertex-ai-search-agent_iam_project_roles[var.project_id])

  project = var.project_id
  role    = each.value
  member  = local.vertex_ai_agent_email
}
