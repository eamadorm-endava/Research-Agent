#!/bin/bash
# scripts/bootstrap-terraform.sh

set -e

# ==============================================================================
# Script: bootstrap.sh
# Purpose:
#   This script is the foundational bootstrapping utility for the GCP project.
#   It initializes the fundamental APIs, creates the Terraform Service Account,
#   assigns all necessary IAM roles, configures Cloud Build 2nd Gen permissions,
#   and sets up the Terraform state bucket in Google Cloud Storage (GCS).
#
# Usage:
#   Ideally, this script should be executed automatically via creation_manager.sh,
#   which handles injecting all necessary parameters.
#   However, it can also be executed manually for isolated bootstrapping by 
#   providing the required CLI flags directly.
#
# Required Parameters (CLI Flags):
#   --project                 - The GCP Project ID where resources will be deployed.
#   --location                - The default GCP region for the state bucket.
#   --sa-name                 - The name of the Service Account to create for Terraform.
#   --admin-user-email        - The email of the primary administrator who needs local impersonation rights to run Terraform directly.
#   --developer-group-email   - The email of the Google Group whose members get impersonation rights.
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- Required Configuration Variables ---
PROJECT_ID=""
LOCATION=""
SA_NAME=""
ADMIN_USER_EMAIL=""
DEVELOPER_GROUP_EMAIL=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --project) PROJECT_ID="$2"; shift ;;
        --location) LOCATION="$2"; shift ;;
        --sa-name) SA_NAME="$2"; shift ;;
        --admin-user-email) ADMIN_USER_EMAIL="$2"; shift ;;
        --developer-group-email) DEVELOPER_GROUP_EMAIL="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

if [[ -z "${PROJECT_ID:-}" ]]; then echo "Error: PROJECT_ID is not set. Use --project"; exit 1; fi
if [[ -z "${LOCATION:-}" ]]; then echo "Error: LOCATION is not set. Use --location"; exit 1; fi
if [[ -z "${SA_NAME:-}" ]]; then echo "Error: SA_NAME is not set. Use --sa-name"; exit 1; fi
if [[ -z "${ADMIN_USER_EMAIL:-}" ]]; then echo "Error: ADMIN_USER_EMAIL is not set. Use --admin-user-email"; exit 1; fi
if [[ -z "${DEVELOPER_GROUP_EMAIL:-}" ]]; then echo "Error: DEVELOPER_GROUP_EMAIL is not set. Use --developer-group-email"; exit 1; fi

export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
BUCKET_NAME="${PROJECT_ID}-terraform-state"

echo "Starting bootstrap for project: $PROJECT_ID"

# 0. Enable fundamental APIs
echo "Enabling fundamental APIs (Service Usage, Resource Manager, Cloud Build)..."
gcloud services enable \
    serviceusage.googleapis.com \
    cloudresourcemanager.googleapis.com \
    cloudbuild.googleapis.com \
    --project=$PROJECT_ID

# 1. Create the Service Account
if ! gcloud iam service-accounts describe $SA_EMAIL --project=$PROJECT_ID > /dev/null 2>&1; then
    echo "Creating Service Account: $SA_NAME..."
    gcloud iam service-accounts create $SA_NAME \
        --display-name="Terraform Management Account" \
        --project=$PROJECT_ID
    
    echo "Waiting for identity propagation (15s)..."
    sleep 15
else
    echo "Service Account $SA_NAME already exists."
fi

# 2. Assign Project-Level Roles to the SA
echo "Assigning infrastructure roles to $SA_NAME..."
ROLES=(
    "roles/serviceusage.serviceUsageAdmin" # To enable APIs
    "roles/iam.serviceAccountAdmin" # To create and manage service accounts
    "roles/resourcemanager.projectIamAdmin" # To manage IAM policies
    "roles/artifactregistry.admin" # To manage Artifact Registry
    "roles/run.admin" # To deploy services to Cloud Run
    "roles/iam.serviceAccountUser" # To allow the SA to act as itself
    "roles/aiplatform.admin" # To deploy the agent to Agent Engine
    "roles/secretmanager.admin" # To create, access, and delete secrets in Secret Manager
    "roles/cloudbuild.admin" # To manage (create and delete) Cloud Build triggers
    "roles/discoveryengine.admin" # To create Auth resources and register agents in Gemini Enterprise
    "roles/dlp.admin" # To manage DLP templates and jobs
    "roles/bigquery.admin" # To manage BigQuery datasets and tables
    "roles/storage.admin" # To manage GCS buckets
    "roles/cloudtasks.admin" # To manage Cloud Tasks queues
)

for ROLE in "${ROLES[@]}"; do
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:$SA_EMAIL" \
        --role="$ROLE" \
        --condition=None
done

# 3. Grant Developer Impersonation (Token Creator)
echo "Granting $DEVELOPER_GROUP_EMAIL the ability to impersonate $SA_NAME..."
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
    --member="group:$DEVELOPER_GROUP_EMAIL" \
    --role="roles/iam.serviceAccountTokenCreator" \
    --project=$PROJECT_ID

# 4. Configure Cloud Build 2nd Gen execution permissions
# ------------------------------------------------------------------------------
# Why this is needed: In Cloud Build 2nd Gen (or when using custom service accounts),
# the default Cloud Build System Agent needs permission to impersonate the custom
# Terraform Service Account. Additionally, the custom SA needs specific roles
# to act as a builder.
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
CB_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-cloudbuild.iam.gserviceaccount.com"

echo "Applying Cloud Build 2nd Gen 'System-to-SA' bridge permissions..."

# 4.1. Grant the Cloud Build System Agent the ability to impersonate the custom SA
# Reason: The internal GCP Cloud Build system runs the triggers, and it must
# have permission to "act as" ($SA_EMAIL) to execute the pipeline steps.
# Note: Google-managed Service Agents can be lazy-provisioned, so we retry the binding.
echo "Waiting for Cloud Build System Agent to be ready (this may take a moment)..."
MAX_RETRIES=12
RETRY_COUNT=0
while ! gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
    --member="serviceAccount:$CB_SERVICE_AGENT" \
    --role="roles/iam.serviceAccountUser" \
    --project=$PROJECT_ID \
    --condition=None > /dev/null 2>&1; do
    
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "Error: Cloud Build Service Agent failed to provision in time."
        exit 1
    fi
    echo "Service Agent not ready yet, retrying in 10s... ($((RETRY_COUNT+1))/$MAX_RETRIES)"
    sleep 10
    RETRY_COUNT=$((RETRY_COUNT+1))
done
echo "Cloud Build System Agent is ready and bound!"

# 4.2. Grant the Cloud Build System Agent its core role
# Reason: Re-asserts that the system agent has the foundational Cloud Build permissions.
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$CB_SERVICE_AGENT" \
    --role="roles/cloudbuild.serviceAgent" \
    --condition=None

# 4.3. Grant the custom SA the explicit 'Builder' role
# Reason: This role (roles/cloudbuild.builds.builder) permits the custom SA 
# to actually execute 'build' resources within the project.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/cloudbuild.builds.builder" \
    --condition=None

# 4.4. Ensure the custom SA can write logs
# Reason: The custom SA must be able to stream execution logs back to Cloud Logging.
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/logging.logWriter" \
    --condition=None

echo "Waiting for identity propagation (15s)..."
sleep 15

# 5. Create GCS Bucket for Terraform State
# Reason: Terraform requires a remote backend to store infrastructure state securely.
if ! gcloud storage buckets describe gs://$BUCKET_NAME > /dev/null 2>&1; then
    echo "Creating GCS bucket for Terraform state: $BUCKET_NAME..."
    gcloud storage buckets create gs://$BUCKET_NAME \
        --project=$PROJECT_ID \
        --location=$LOCATION \
        --uniform-bucket-level-access

    echo "Enabling versioning on bucket..."
    gcloud storage buckets update gs://$BUCKET_NAME --versioning
else
    echo "Bucket $BUCKET_NAME already exists."
fi

# 6. Grant individual user impersonation
# Reason: Allows the developer running this script to act as the Terraform SA locally.
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --member="user:$ADMIN_USER_EMAIL" \
  --role="roles/iam.serviceAccountUser" \
  --project="$PROJECT_ID"

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --member="user:$ADMIN_USER_EMAIL" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project="$PROJECT_ID"

echo "Waiting for IAM impersonation roles to propagate..."
MAX_RETRIES=12
RETRY_COUNT=0
while ! gcloud auth print-access-token --impersonate-service-account="$SA_EMAIL" > /dev/null 2>&1; do
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "Error: IAM impersonation failed to propagate in time."
        exit 1
    fi
    echo "Impersonation not ready yet, retrying in 10s... ($((RETRY_COUNT+1))/$MAX_RETRIES)"
    sleep 10
    RETRY_COUNT=$((RETRY_COUNT+1))
done

echo "Bootstrap complete! IAM, Service Accounts, and State Bucket are ready."
echo "To use this locally, run: gcloud auth application-default login --impersonate-service-account=$SA_EMAIL"