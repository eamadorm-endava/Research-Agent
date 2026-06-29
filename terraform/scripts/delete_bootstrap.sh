#!/bin/bash
# scripts/delete_bootstrap.sh

# Exit on error
set -euo pipefail

# -----------------------------------------------------------------------------
# Bootstrap Deletion Script
# -----------------------------------------------------------------------------
# This script deletes the Terraform state bucket and the Terraform service account.
# Note: CI/CD triggers are handled by cicd_triggers_deletion.sh.
#
# Run this script from the repository root:
#   ./terraform/scripts/delete_bootstrap.sh --project <PROJECT_ID> --sa-name <SA_NAME>
#
# Required parameters:
#   --project            GCP Project ID.
#   --sa-name            The base name of the Terraform service account.
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- Configuration ---
PROJECT_ID=""
SA_NAME="terraform-sa-gemini-project"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --project) PROJECT_ID="$2"; shift ;;
        --sa-name) SA_NAME="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

if [[ -z "$PROJECT_ID" ]] || [[ -z "$SA_NAME" ]]; then
    echo "Error: --project and --sa-name parameters are required."
    exit 1
fi

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "This will delete the Terraform State Bucket and the Terraform Service Account in project: $PROJECT_ID"
echo "Parameters:"
echo "  - SA Name: $SA_NAME"
read -p "Are you sure you want to proceed? (y/N): " confirm

if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo "---------------------------------------"
echo "Deleting Terraform State Bucket..."
BUCKET_NAME="${PROJECT_ID}-terraform-state"
if gcloud storage buckets describe "gs://$BUCKET_NAME" --project="$PROJECT_ID" > /dev/null 2>&1; then
    # Recursively delete the bucket and any residual state files
    gcloud storage rm --recursive "gs://$BUCKET_NAME" --project="$PROJECT_ID" --quiet
    echo "Bucket gs://$BUCKET_NAME deleted."
else
    echo "Bucket gs://$BUCKET_NAME does not exist."
fi

echo "---------------------------------------"
echo "Cleaning up IAM Bindings and Deleting Service Account..."
echo "Cleaning up IAM Bindings for $SA_EMAIL (including deleted tombstones)..."
# Get all exact member strings matching this service account (active or deleted)
MEMBERS=$(gcloud projects get-iam-policy "$PROJECT_ID" \
    --flatten="bindings[].members" \
    --format="value(bindings.members)" \
    --filter="bindings.members:$SA_EMAIL" | sort -u)

for MEMBER in $MEMBERS; do
    if [[ -n "$MEMBER" ]]; then
        ROLES=$(gcloud projects get-iam-policy "$PROJECT_ID" \
            --flatten="bindings[].members" \
            --format="value(bindings.role)" \
            --filter="bindings.members:$MEMBER")
        
        for ROLE in $ROLES; do
            echo "Removing role: $ROLE for $MEMBER"
            gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
                --member="$MEMBER" \
                --role="$ROLE" \
                --quiet > /dev/null 2>&1 || echo "Warning: Failed to remove role $ROLE for $MEMBER"
        done
    fi
done

echo "Removing Cloud Build System Agent role from project..."
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
CB_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$CB_SERVICE_AGENT" \
    --role="roles/cloudbuild.serviceAgent" \
    --quiet > /dev/null 2>&1 || echo "Warning: Failed to remove Cloud Build System Agent role."

if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" > /dev/null 2>&1; then
    gcloud iam service-accounts delete "$SA_EMAIL" --project="$PROJECT_ID" --quiet
    echo "Service Account $SA_EMAIL deleted."
else
    echo "Service Account $SA_EMAIL is already physically deleted."
fi

echo "---------------------------------------"
echo "Cleanup complete! Your project is now ready for a fresh bootstrap."
echo ""
echo "================================================================="
echo "IMPORTANT MANUAL STEP REQUIRED:"
echo "Please navigate to the Google Cloud Console -> Cloud Build -> Repositories"
echo "and manually delete the connection between Cloud Build and your GitHub repository,"
echo "as this cannot be cleanly automated via the CLI."
echo "================================================================="