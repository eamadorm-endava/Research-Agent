mock_provider "google" {}
mock_provider "google-beta" {}

variables {
  project_id             = "test-project"
  main_region            = "us-central1"
  developers_group_email = "devs@example.com"

  apis_to_enable = {
    "test-project" = [
      "storage.googleapis.com",
      "run.googleapis.com",
      "artifactregistry.googleapis.com"
    ]
  }

  mcp_server_service_account_name = "gcs-mcp-server"
  mcp_server_iam_project_roles = {
    "test-project" = ["roles/storage.objectViewer"]
  }

  artifact_registry_name = "mcp-servers"

  mcp_server_cloud_run_name      = "gcs-mcp-server"
  mcp_server_cloud_run_image_tag = "latest"
  mcp_server_cloud_run_env = {
    LOG_LEVEL = "INFO"
  }
}

run "plan_defaults" {
  command = plan

  assert {
    condition     = local.cloud_run_region == "us-central1"
    error_message = "Expected Cloud Run region to default to main_region when mcp_server_cloud_run_region is null."
  }

  assert {
    condition     = local.cloud_run_image == "us-central1-docker.pkg.dev/test-project/mcp-servers/gcs-mcp-server"
    error_message = "Expected Cloud Run image path to match registry + service naming convention."
  }
}

run "plan_with_explicit_region" {
  command = plan

  variables {
    mcp_server_cloud_run_region = "northamerica-northeast1"
  }

  assert {
    condition     = local.cloud_run_region == "northamerica-northeast1"
    error_message = "Expected Cloud Run region to use explicit mcp_server_cloud_run_region when provided."
  }
}
