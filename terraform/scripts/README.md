## Infrastructure Bootstrap Script

This README is designed to provide a professional overview of your automation script, ensuring that any developer on your team understands the "why" and "how" of the infrastructure setup.

`bootstrap.sh` automates the initial setup of Google Cloud Platform resources required to run Terraform through Cloud Build.

Its goal is to establish a least-privilege setup where a dedicated service account manages infrastructure, while developers and CI/CD pipelines use impersonation instead of static JSON keys.

## Requirements
Before running the script, ensure the following conditions are met:

1. GCP permissions:

    - You must have Owner or Editor plus Project IAM Admin on the account you are using.
    - You must be allowed to impersonate the Terraform service account. The script grants this access after you set `USER_EMAIL` correctly.

2. The Google Cloud SDK must be installed and authenticated (gcloud auth login).

3. GitHub connection:

    - The `Research-Agent` repository must already be connected to Cloud Build in GCP.
    - Check Cloud Build > Triggers > Manage Repositories.

4. Developer group: the developer Google Group must already exist in your organization.

## Architecture Flow
The script performs the following steps:

1. Creates the Terraform service account.
2. Waits briefly for IAM propagation.
3. Grants the service account the roles required to manage APIs, IAM policies, and project resources.
4. Grants impersonation access to the developer group and Cloud Build service account.
5. Enables the Cloud Build API.
6. Prepares Terraform automation prerequisites.

## Execution Guide

1. Make the script executable:

```
chmod +x terraform/scripts/bootstrap.sh
```
2. Run the script from the repository root:

```
./terraform/scripts/bootstrap.sh
```

Or use Make targets from repository root:

```
make bootstrap
make bootstrap-no-shared
```
3. For local impersonation after setup:

```
gcloud auth application-default login --impersonate-service-account="SERVICE_ACCOUNT_EMAIL"
```

## Trigger-Only Setup (Run Once)

Use `run_once.sh` when you only want to create MCP Cloud Build triggers without rerunning the full bootstrap:

```
chmod +x terraform/scripts/run_once.sh
./terraform/scripts/run_once.sh
```

From repository root you can also use:

```
make run-once-terraform-triggers
```

By default it creates or verifies:
- `bq-mcp-server-services-plan`
- `bq-mcp-server-services-apply`
- `gcs-mcp-server-services-plan`
- `gcs-mcp-server-services-apply`

`shared_resources` is intentionally not on a trigger flow. Apply it once during bootstrap/manual setup.

If a trigger already exists but still points to an old build config path, recreate it in place:

```
FORCE_RECREATE=true ./terraform/scripts/run_once.sh
```

## One-Time Shared Resources Apply

Apply `shared_resources` once during bootstrap/manual setup (not via trigger flow):

```
cd terraform/shared_resources
terraform init -reconfigure \
    -backend-config="bucket=<PROJECT_ID>-terraform-state" \
    -backend-config="prefix=terraform/state/shared-resources"
terraform plan
terraform apply
```

`bootstrap.sh` runs this sequence by default. To skip this step when needed:

```
APPLY_SHARED_RESOURCES=false ./terraform/scripts/bootstrap.sh
```

## Trigger-Only Setup (Run Once)

Use `run_once.sh` when you only want to create MCP Cloud Build triggers (without running full bootstrap):

```
chmod +x terraform/scripts/run_once.sh
./terraform/scripts/run_once.sh
```

By default it creates/ensures:
- `bq-mcp-server-services-plan`
- `bq-mcp-server-services-apply`
- `gcs-mcp-server-services-plan`
- `gcs-mcp-server-services-apply`

If a trigger already exists but still points to an old build config path, recreate it in place:

```
FORCE_RECREATE=true ./terraform/scripts/run_once.sh
```

## Terraform Infrastructure Access Setup

### Service Account
- **Name:** `terraform-sa-gemini-project`  
- **Purpose:** The primary identity for infrastructure management.

---

### IAM Roles Assigned

| Role | Role ID | Why It's Needed |
|------|---------|----------------|
| Service Usage Admin | `roles/serviceusage.serviceUsageAdmin` | Required to enable and disable Google Cloud APIs. |
| Service Account Admin | `roles/iam.serviceAccountAdmin` | Allows Terraform to manage other service accounts. |
| Project IAM Admin | `roles/resourcemanager.projectIamAdmin` | Required to assign roles at the project level. |
| Service Account Token Creator | `roles/iam.serviceAccountTokenCreator` | Enables impersonation for developers and Cloud Build. |

---

### Additional Resources

| Resource | Name / Scope | Purpose |
|----------|--------------|----------|
| Cloud Build Triggers | MCP plan/apply triggers | Automates CI/CD workflows for MCP Terraform folders. |

##  Cleanup
To remove resources created by these scripts:

```
./terraform/scripts/cleanup.sh
```