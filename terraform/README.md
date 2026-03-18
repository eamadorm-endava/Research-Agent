## Infrastructure Management

This directory contains the Terraform configurations and bootstrap scripts used to manage Research-Agent infrastructure on Google Cloud Platform.

## Prerequisites and Required Permissions

Before running any scripts, ensure your active account has the following IAM roles at the project level:

- `roles/resourcemanager.projectIamAdmin` to manage service account permissions
- `roles/iam.serviceAccountAdmin` to create the Terraform service account
- `roles/serviceusage.serviceUsageAdmin` to enable APIs
- `roles/storage.admin` to create the Terraform state bucket


## Infrastructure Deployment Workflow

The environment uses a dedicated service account and a GCS backend to manage Terraform state securely through Cloud Build.

1. Open a terminal.

2. Navigate to the scripts folder:

```
cd terraform/scripts
```

3. Review [terraform/scripts/README.md](scripts/README.md).

4. Execute the bootstrap script when you need to create the Terraform service account, state bucket, and baseline Cloud Build setup.

The bootstrap script creates the Terraform service account, grants required IAM roles, creates the state bucket, and prepares Cloud Build integration.

## Terraform Project Structure

| Folder                | Description                                              |
|-----------------------|----------------------------------------------------------|
| `base_modules/`       | Reusable modules (IAM, APIs, Networking).               |
| `ai_agent_resources/` | Service Accounts and APIs for the AI Agent.             |
| `bq_mcp_server_resources/` | BigQuery MCP service resources.                  |
| `gcs_mcp_server_resources/` | GCS MCP service resources.                      |
| `shared_resources/` | Shared infrastructure such as Artifact Registry.         |

## Apply Order

Apply shared infrastructure before service-specific MCP modules:

1. `shared_resources/`
2. `ai_agent_resources/` as needed
3. `bq_mcp_server_resources/`
4. `gcs_mcp_server_resources/`

This order ensures the shared `mcp-servers` Artifact Registry repository is owned by a single Terraform state before the MCP service modules consume it.

## Module Guides

- AI Agent Services: View README.md inside ai_agent_resources folder
- BigQuery MCP Resources: View README.md inside bq_mcp_server_resources folder
- GCS MCP Resources: View README.md inside gcs_mcp_server_resources folder
- Shared Resources: View README.md inside shared_resources folder

## CI/CD Workflow

Infrastructure is deployed automatically via Cloud Build:

1. CI (`terraform plan`) is triggered when a pull request is opened against `main`.
2. CD (`terraform apply`) is triggered when code is merged or pushed to `main`.
3. Trigger creation is managed outside Terraform with `terraform/scripts/run_once.sh` for `bq_mcp_server_resources` and `gcs_mcp_server_resources`.
4. `shared_resources` is applied one-time during bootstrap/manual setup (not continuous CI/CD).