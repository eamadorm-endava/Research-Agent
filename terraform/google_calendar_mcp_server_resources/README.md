# Google Calendar MCP Server Resources

### Overview

This directory contains the Terraform configuration for the Google Calendar (and Google Meet) MCP server.

This module manages API enablement, the service account used by the Google Calendar MCP service, and the Cloud Run deployment for the server.

## IAM Architecture
For this MCP, authentication with Calendar/Meet is handled via OAuth tokens rather than Google Cloud systemic IAM roles. Therefore, the created Service Account (`calendar-mcp-server`) deliberately has an empty set of IAM roles (`iam_project_roles = {}`) to adhere to the principle of least privilege. Its primary purpose is to serve as the secure identity execution environment for the Cloud Run service in order to avoid relying on the default Compute Engine service account.

## APIs

The following APIs are managed (enabled) by this module. These APIs must be enabled before deploying the MCP Server in any GCP project:

- `calendar-json.googleapis.com`
- `meet.googleapis.com`

Nevertheless, the following APIs are required for the MCP Server to function, but they are not managed by this module (are managed by the `terraform/scripts/bootstrap.sh` script) due to those are used by multiple MCP servers:

- `run.googleapis.com`
- `artifactregistry.googleapis.com`

## Service Accounts Overview

| Service Account Name  | Status  | Description | Permissions Assigned |
|-----------------------|---------|-------------|----------------------|
| `calendar-mcp-server` | Created | Service account used by the Calendar/Meet MCP server on Cloud Run. | None (Relies on OAuth) |

## CI/CD workflow

This project uses Google Cloud Build for automated deployments defined via YAML parameterization schemas:

1. **Feature Branches:** Create a branch for your changes (e.g., `feature/calendar-integrations`).
2. **Pull Request:** Opening a PR to `main` triggers a complete CI execution (`mcp-server-services-cloud-build-ci.yaml`):
    - Code quality tools (`make run-precommit`).
    - Unit tests (`make run-calendar-tests`).
    - Docker container virtualized build validation.
    - Security-compliant `terraform plan`.
    - Note: The PR cannot be merged if any of the checks (especially formatting/linting) fail.
3. **Merge to Main:** Merging the PR triggers the Continuous Deployment phase (`mcp-server-services-cloud-build-cd.yaml`):
    - Parallel `docker push` tagging both the `${COMMIT_SHA}` and `latest`.
    - Live updates in the Dev environment orchestrating `terraform apply tfplan`.

## Usage

To enable services, define the `apis_to_enable` variable in your `terraform.tfvars` file. The module will automatically iterate through each project and enable the listed services.

To generate the CI/CD triggers on the GCP project, execute the unified shell script at the repository root:

```bash
chmod +x terraform/scripts/cicd_triggers_creation.sh
./terraform/scripts/cicd_triggers_creation.sh
```

## Variables Reference

| Name | Description | Type | Default | Required |
|---|---|---|---|:---:|
| `project_id` | The ID of the project where resources are managed. | `string` | n/a | yes |
| `main_region` | The main region to create the resources. | `string` | `"us-central1"` | no |
| `apis_to_enable` | Service APIs to enable, mapped by project ID. | `map(list(string))` | `{}` | yes |
| `mcp_server_service_account_name` | The name of the Service Account created for the Cloud Run instance. | `string` | n/a | yes |
| `mcp_server_iam_project_roles` | Map of project IDs to a list of roles to be assigned to the Service Account. | `map(list(string))` | `{}` | yes |
| `artifact_registry_name` | The name of the Artifact Registry repository holding the Docker images. | `string` | n/a | yes |
| `mcp_server_cloud_run_name` | The physical name of the GCP Cloud Run service in the console. | `string` | n/a | yes |
| `mcp_server_cloud_run_image_tag` | The tag/sha of the Docker image to deploy dynamically on Cloud Run. | `string` | n/a | yes |
| `mcp_server_cloud_run_env` | Environment parameters mapped directly into Cloud Run. | `map(string)` | `{}` | no | 
 