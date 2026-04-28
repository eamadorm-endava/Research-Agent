#!/bin/bash
# Script to delete manual infrastructure for Stage 1 Prototyping

ARTIFACT_BUCKET="ai_agent_landing_zone"

echo "Deleting GCS Bucket: gs://${ARTIFACT_BUCKET}"

if gcloud storage buckets describe gs://${ARTIFACT_BUCKET} > /dev/null 2>&1; then
    gcloud storage buckets delete gs://${ARTIFACT_BUCKET} --quiet
    echo "Bucket deleted successfully."
else
    echo "Bucket does not exist."
fi
