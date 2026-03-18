# Shared Resources

This Terraform module manages infrastructure shared across multiple services.

Currently it owns the shared Artifact Registry repository `mcp-servers`, which is used to store Docker images for multiple MCP servers.

## Import Behavior

The configuration includes a Terraform `import` block for the repository, so if `mcp-servers` already exists in GCP it is imported into this state automatically during plan/apply.

## Ownership Model

- `shared_resources/` owns the Artifact Registry repository.
- `bq_mcp_server_resources/` and `gcs_mcp_server_resources/` only reference the repository name when building image URLs.

## Usage

Run from this directory:

```bash
terraform init -reconfigure \
	-backend-config="bucket=<PROJECT_ID>-terraform-state" \
	-backend-config="prefix=terraform/state/shared-resources"
terraform plan
terraform apply
```

If Terraform unexpectedly plans to destroy BQ/GCS resources from this folder, it is using the wrong backend state key. Re-run `terraform init -reconfigure` with the `shared-resources` prefix above.

Apply this module before `bq_mcp_server_resources` and `gcs_mcp_server_resources` so the shared `mcp-servers` repository is already present in Terraform state.

This module is intended as a one-time bootstrap/manual apply, not a continuous trigger-based CI/CD flow.