# Creation Manager Deep Dive: Step by Step

The `creation_manager.sh` script is the central entry point for deploying the Research-Agent ecosystem. This document explains the exact execution flow, the parameters it requires, the variables it computes internally, and how it delegates actions to underlying scripts.

## 1. Input Parameters

The script accepts CLI flags to dynamically toggle components on or off.

**Global Requirements:**
- `--project`: Target GCP Project ID
- `--region`: Default GCP Region

**Component Toggles & Context:**
- **Bootstrap (`--deploy-bootstrap`)**: Requires `--sa-name`, `--admin-user-email`, `--developer-group-email`, `--github-connection-name`, `--repository-slug`
- **Shared Resources (`--deploy-shared-resources`)**: Relies on global parameters.
- **Gemini Enterprise App (`--deploy-ge-app`)**: Requires `--ge-app-location`. Optionally accepts `--ge-app-name-suffix` (defaults to `osiris-app`).
- **AI Agent (`--deploy-ai-agent`)**: Accepts `--agent-engine-location` (defaults to global `--region`).
- **MCP Servers (`--deploy-mcp-servers`)**: Requires `--mcp-servers-to-deploy`, formatted as `all` or a comma-separated list like `bq=us-east1,gcs`.
- **Pipelines (`--deploy-ekb-pipeline`)**: Relies on global parameters.
- **CI/CD Triggers**: Accepts `--force-recreate` to wipe existing triggers before building.

---

## 2. Dynamic Variable Computation

Before executing any infrastructure changes, the script pre-computes several dependency variables.

- **`AGENT_ENGINE_LOCATION`**: If not provided via CLI, it automatically falls back to the global `REGION`.
- **`GE_APP_ID`**: Computed by concatenating strings: `${PROJECT_ID}-${GE_APP_LOCATION}-${GE_APP_NAME_SUFFIX}`.
- **`AGENT_DISPLAY_NAME`**: Dynamically extracted directly from the target `ai-agent-services-cloud-build-cd.yaml` file using `grep` and regex parsing to ensure the orchestrator uses exactly the same name the CI/CD pipeline will deploy.
- **`PROJECT_NUMBER`**: Dynamically fetched via the `gcloud projects describe` API.
- **Server Specific Regions**: The script parses the `--mcp-servers-to-deploy` string (e.g., `bq=us-east1`). If a region is specified per-server, it extracts it; otherwise, it defaults to the global `REGION`.
- **Cloud Run URLs**: Every single service URL is mathematically computed in advance based on the format: `https://[server-prefix]-${PROJECT_NUMBER}.[SERVER_REGION].run.app` (e.g., `BQ_URL`, `SHAREPOINT_URL`, `OUTLOOK_URL`, `EKB_URL`).

---

## 3. Pre-Flight Validation & Summary

After calculating the necessary variables, the script:
1. Validates that no required flags are missing based on the boolean features requested.
2. Prints a detailed console summary showing the requested components and the computed internal IDs.
3. Stops and prompts the user `(y/N)` to explicitly confirm execution before proceeding.
4. Executes `gcloud config set project` to ensure the session operates in the correct workspace.

---

## 4. Execution Flow

| Execution Order | Script (Description) | Parameters | Output |
| :---: | :--- | :--- | :--- |
| **1** | `bootstrap.sh`<br/>*(Provisions foundational GCP APIs, main Terraform SA, TF State Bucket, and establishes GitHub Connection)* | **CLI Flags:**<br/>`--project`: The target GCP Project ID<br/>`--location`: The default GCP region for resources<br/>`--sa-name`: Name of the Terraform service account<br/>`--admin-user-email`: Email of the primary administrator who needs local impersonation rights to run Terraform directly<br/>`--developer-group-email`: Developer group for IAM bindings | Enabled APIs, IAM Role Bindings, GitHub App Connection |
| **2** | `terraform apply`<br/>*(Executes IaC for Shared Resources like Secret Manager, Artifact Registry, and Landing Zone bucket)* | **Terraform Variables:**<br/>`project_id`: Target GCP Project ID<br/>`main_region`: Default deployment region<br/>`bucket`: Name of the GCS bucket for Terraform backend state | Deployed Shared Resources |
| **3** | `cicd_triggers_creation.sh`<br/>*(Creates Cloud Build triggers dynamically for Shared Resources, AI Agent, EKB Pipeline, and all MCP Servers)* | **CLI Flags:**<br/>`--project`: Target GCP Project ID<br/>`--region`: Default GCP Region<br/>`--sa-name`: Service Account Name<br/>`--sa-email`: Service Account Email<br/>`--github-connection`: GitHub Connection Name<br/>`--repo-slug`: GitHub Repository Slug<br/>`--deploy-shared-resources`: Toggle for Shared Resources triggers<br/>`--ge-app-location`: Location for the Gemini Enterprise App<br/>`--ge-app-name-suffix`: Unique suffix for the GE App ID<br/>`--force-recreate`: Flag to overwrite existing triggers<br/>`--[server]-url`: Pre-computed Cloud Run URL for each MCP server | Cloud Build Triggers with static substitution variables attached |
| **4** | `gcloud builds triggers run`<br/>*(Triggers the automated deployment of all configured MCP Servers and the EKB Pipeline)* | **CLI Flags:**<br/>`--trigger-id`: The specific Cloud Build trigger name to execute | Cloud Run Services (BQ, GCS, SharePoint, Outlook, etc.) |
| **5** | `ge_agent_manager.sh provision-app`<br/>*(Provisions the base Gemini Enterprise application environment)* | **CLI Flags:**<br/>`--project`: Target GCP Project ID<br/>`--ge-location`: Regional API endpoint for GE<br/>`--app-id`: Computed unique identifier for the GE App | Gemini Enterprise App ID Registration and base settings |
| **6** | `gcloud builds triggers run`<br/>*(Triggers the deployment of the AI Agent to Vertex AI Agent Engine)* | **CLI Flags:**<br/>`--trigger-id`: ai-agent-services-cd | Deployed Vertex AI Agent Engine Service linked to the GE App |
