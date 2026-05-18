#!/bin/bash
# scripts/clean.sh

# Exit on error
set -e

PROJECT_ID="ag-core-ops-auj0"
SA_EMAIL="terraform-sa-gemini-project@${PROJECT_ID}.iam.gserviceaccount.com"

echo "This will delete all Cloud Build triggers and the Terraform Service Account in project: $PROJECT_ID"
read -p "Are you sure you want to proceed? (y/N): " confirm

if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

# Note: Cloud build trigger names must match with names thar was created from the bootstrap.sh script
# List of triggers created in cicd_triggers_creation.sh
TRIGGERS=(
    "ai-agent-services-plan"
    "ai-agent-services-apply"
    "bq-mcp-server-services-plan"
    "bq-mcp-server-services-apply"
    "gcs-mcp-server-services-plan"
    "gcs-mcp-server-services-apply"
    "drive-mcp-server-services-plan"
    "drive-mcp-server-services-apply"
    "calendar-mcp-server-services-plan"
    "calendar-mcp-server-services-apply"
    "ekb-pipeline-services-plan"
    "ekb-pipeline-services-apply"
)

echo "---------------------------------------"
echo "Deleting specific Cloud Build Triggers..."

for TRIGGER in "${TRIGGERS[@]}"; do
    if gcloud builds triggers describe "$TRIGGER" --region=us-central1 --project=$PROJECT_ID > /dev/null 2>&1; then
        echo "Deleting trigger: $TRIGGER..."
        gcloud alpha builds triggers delete "$TRIGGER" --region=us-central1 --project=$PROJECT_ID --quiet
    else
        echo "Trigger $TRIGGER not found, skipping."
    fi
done
echo "Trigger cleanup complete."

echo "---------------------------------------"
echo "Deleting Service Account..."
if gcloud iam service-accounts describe $SA_EMAIL --project=$PROJECT_ID > /dev/null 2>&1; then
    gcloud iam service-accounts delete $SA_EMAIL --project=$PROJECT_ID --quiet
    echo "Service Account $SA_EMAIL deleted."
else
    echo "Service Account $SA_EMAIL does not exist."
fi

echo "---------------------------------------"
echo "Cleanup complete! Your project is now ready for a fresh bootstrap."