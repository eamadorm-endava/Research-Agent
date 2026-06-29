#!/bin/bash
# scripts/delete_bootstrap.sh

# Exit on error
set -euo pipefail

# -----------------------------------------------------------------------------
# Bootstrap Deletion Script
# -----------------------------------------------------------------------------
# This script deletes all Cloud Build triggers created during bootstrap and
# the Terraform service account.
#
# Run this script from the repository root:
#   ./terraform/scripts/delete_bootstrap.sh --project <PROJECT_ID> --region <REGION> --sa-name <SA_NAME> --trigger-bases <BASES>
#
# Required parameters:
#   --project            GCP Project ID.
#   --region             GCP Region where the triggers exist.
#   --sa-name            The base name of the Terraform service account.
#   --trigger-bases      Comma-separated list of the base names for the triggers (e.g. "ai-agent,bq-mcp-server").
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- Configuration ---
PROJECT_ID="prd-ge-prod-endava-01-yd8e-1"
REGION="us-central1"
SA_NAME="terraform-sa-gemini-project"
TRIGGER_BASES_STR="ai-agent,bq-mcp-server,gcs-mcp-server,drive-mcp-server,calendar-mcp-server,ekb-pipeline,onedrive-mcp-server,sharepoint-mcp-server,atlassian-mcp-server,outlook-mcp-server"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --project) PROJECT_ID="$2"; shift ;;
        --region) REGION="$2"; shift ;;
        --sa-name) SA_NAME="$2"; shift ;;
        --trigger-bases) TRIGGER_BASES_STR="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

if [[ -z "$PROJECT_ID" ]] || [[ -z "$REGION" ]] || [[ -z "$SA_NAME" ]] || [[ -z "$TRIGGER_BASES_STR" ]]; then
    echo "Error: --project, --region, --sa-name, and --trigger-bases parameters are all required."
    exit 1
fi

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "This will delete all Cloud Build triggers and the Terraform Service Account in project: $PROJECT_ID"
echo "Parameters:"
echo "  - Region: $REGION"
echo "  - SA Name: $SA_NAME"
echo "  - Trigger Bases: $TRIGGER_BASES_STR"
read -p "Are you sure you want to proceed? (y/N): " confirm

if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

# Convert the comma-separated string into an array
IFS=',' read -ra TRIGGER_BASES <<< "$TRIGGER_BASES_STR"

echo "---------------------------------------"
echo "Deleting specific Cloud Build Triggers..."

for BASE in "${TRIGGER_BASES[@]}"; do
    for SUFFIX in "services-plan" "services-apply"; do
        TRIGGER="${BASE}-${SUFFIX}"
        if gcloud builds triggers describe "$TRIGGER" --region="$REGION" --project="$PROJECT_ID" > /dev/null 2>&1; then
            echo "Deleting trigger: $TRIGGER..."
            gcloud builds triggers delete "$TRIGGER" --region="$REGION" --project="$PROJECT_ID" --quiet
        else
            echo "Trigger $TRIGGER not found, skipping."
        fi
    done
done
echo "Trigger cleanup complete."

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
if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" > /dev/null 2>&1; then
    echo "Removing IAM bindings for $SA_EMAIL..."
    ROLES=$(gcloud projects get-iam-policy "$PROJECT_ID" \
        --flatten="bindings[].members" \
        --format="value(bindings.role)" \
        --filter="bindings.members:serviceAccount:$SA_EMAIL")
    
    for ROLE in $ROLES; do
        echo "Removing role: $ROLE"
        gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
            --member="serviceAccount:$SA_EMAIL" \
            --role="$ROLE" \
            --quiet > /dev/null 2>&1 || echo "Warning: Failed to remove role $ROLE"
    done

    gcloud iam service-accounts delete "$SA_EMAIL" --project="$PROJECT_ID" --quiet
    echo "Service Account $SA_EMAIL deleted."
else
    echo "Service Account $SA_EMAIL does not exist."
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