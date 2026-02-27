# API Manager Module

### Overview
This module manages the activation of Google Cloud Service APIs. It is designed to be the first step in the deployment pipeline, ensuring all necessary services are enabled before other resources are managed.

This module enables Google Cloud Platform Service APIs across one or more projects. It uses a flattened data structure to efficiently manage multiple APIs via a single variable map.

## Usage

To enable services, define the `project_services` variable in your `terraform.tfvars` file. The module will automatically iterate through each project and enable the listed services.

## Deployment Permissions

Because this specific deployment is executed via Cloud Build, the Cloud Build Service Account requires the following permission  at project level or folder level for every project defined in the project's enabled services:

| Role | Role ID | Why it's needed |
| :--- | :--- | :--- |
| **Service Usage Admin** | `roles/serviceusage.serviceUsageAdmin` | Required to enable and disable Google Cloud APIs. |

## CI/CD workflow

This project uses Google Cloud Build for automated deployments:

1. **Feature Branches:** Create a branch for your changes (e.g., `feature/add-sa-roles`).
2. **Pull Request:** Opening a PR to `main` triggers a `terraform plan`.
   - View the results in the GitHub "Checks" tab or GCP Cloud Build history.
   - The PR cannot be merged if the plan fails.
   - The PR required one approvers at least
3. **Merge to Main:** Merging the PR triggers `terraform apply`.
   - Ensure the plan was reviewed before merging.

## Variables

| Name | Description | Type | Default | Required |
|---|---|---|---|:---:|
| `project_services` | Service APIs to enable, mapped by project ID. | `map(list(string))` | `{}` | yes |