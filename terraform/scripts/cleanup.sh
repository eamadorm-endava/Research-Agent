#!/bin/bash
# scripts/clean.sh

# Exit on error
set -e

PROJECT_ID="p-dev-gce-60pf"
SA_EMAIL="terraform-sa-gemini-project@${PROJECT_ID}.iam.gserviceaccount.com"

echo "This will delete all Cloud Build triggers and the Terraform Service Account in project: $PROJECT_ID"
read -p "Are you sure you want to proceed? (y/N): " confirm

if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

# Note: Cloud build trigger names must match with names thar was created from the bootstrap.sh script
echo "---------------------------------------"
echo "Deleting Cloud Build Triggers..."
# Using '-' before the command or '|| true' allows the script to continue if a trigger is already gone
gcloud beta builds triggers delete ai-agent-resources-plan --region=us-central1 --project=$PROJECT_ID --quiet || echo "ai-agent-resources-plan not found."
gcloud beta builds triggers delete ai-agent-resources-apply --region=us-central1 --project=$PROJECT_ID --quiet || echo "ai-agent-resources-apply not found."
gcloud beta builds triggers delete mcp-server-service-plan --region=us-central1 --project=$PROJECT_ID --quiet || echo "mcp-server-service-plan not found."
gcloud beta builds triggers delete mcp-server-service-apply --region=us-central1 --project=$PROJECT_ID --quiet || echo "mcp-server-service-apply not found."

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