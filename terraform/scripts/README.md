##  Infrastructure Bootstrap Script
### Overview
The bootstrap.sh script automates the initial setup of Google Cloud Platform (GCP) resources required to run Terraform via Cloud Build.

Its primary goal is to establish a secure "Least Privilege" environment where a dedicated Service Account manages infrastructure, while developers and CI/CD pipelines use Identity Federation (Impersonation) instead of static JSON keys.

Gemini ha dicho
This README is designed to provide a professional overview of your automation script, ensuring that any developer on your team understands the "why" and "how" of the infrastructure setup.

Infrastructure Bootstrap Script
Purpose
The bootstrap.sh script automates the initial setup of Google Cloud Platform (GCP) resources required to run Terraform via Cloud Build.

Its primary goal is to establish a secure "Least Privilege" environment where a dedicated Service Account manages infrastructure, while developers and CI/CD pipelines use Identity Federation (Impersonation) instead of static JSON keys.

## Requirements
Before running the script, ensure the following conditions are met:

1. GCP Permissions: 

    - You must have Owner or Editor + Project IAM Admin roles on the user account or the sa that you need to work.
    - You must have permissions to impersonate the Terraform service account (Need to have roles/iam.serviceAccountUser), this IAM role is assigned in the script you must only need to setup the parameter `USER_EMAIL` with your GCP email.

2. The Google Cloud SDK must be installed and authenticated (gcloud auth login).

3. GitHub Connection:

    - The GitHub repository Research-Agent must be manually connected to Cloud Build in the GCP Console.

    - Navigate to: Cloud Build > Triggers > Manage Repositories to ensure the connection exists.

6. Developer Group: The group for developers must exist in your Google Workspace/Organization.

## Architecture Flow
The script executes the following logical steps to secure and automate the environment:

1. Identity Creation: Creates the terraform-sa-gemini-project Service Account.

2. Propagation Buffer: Pauses for 15 seconds to ensure the global IAM system recognizes the new identity.

3. Infrastructure Permissions: Grants the Service Account authority to manage APIs, IAM policies, and Project resources.

4. Impersonation Setup:

    - Grants the Developer Group the Service Account Token Creator role.

    -  Grants the Cloud Build Service Account the same role.

5. API Activation: Enables the cloudbuild.googleapis.com service.

6. CI/CD Automation: Creates four GitHub-connected triggers (2 for Plan/PR and 2 for Apply/Merge) targeting specific Terraform directories.

## Execution Guide

1. Set Permissions
Ensure the script is executable:

```
Bash

chmod +x scripts/bootstrap-terraform.sh
```
2. Run the Script
Execute the script from the root of the repository:

```
Bash

./scripts/bootstrap-terraform.sh
```
3. Local Impersonation
After a successful run, developers do not need local keys. To run Terraform locally using the newly created identity, run:

```
Bash

gcloud auth application-default login --impersonate-service-account="the sa name that you defined" (example: terraform-sa-gemin)
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
| Cloud Build Triggers | `api-services`, `service-accounts` | Automates CI/CD workflows for Terraform folders. |

##  Cleanup
To remove all resources created by this script:

```
Bash

./scripts/clean.sh
```