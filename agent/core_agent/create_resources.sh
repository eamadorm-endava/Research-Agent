#!/bin/bash
# Script to create manual infrastructure for Stage 1 Prototyping

PROJECT_ID=$(gcloud config get-value project)
LOCATION="us-central1"
ARTIFACT_BUCKET="ai_agent_landing_zone"

echo "Creating GCS Bucket: gs://${ARTIFACT_BUCKET} in project ${PROJECT_ID}"

# Create the bucket if it doesn't exist
if ! gcloud storage buckets describe gs://${ARTIFACT_BUCKET} > /dev/null 2>&1; then
    gcloud storage buckets create gs://${ARTIFACT_BUCKET} --location=${LOCATION} --uniform-bucket-level-access
    echo "Bucket created successfully."
else
    echo "Bucket already exists."
fi
