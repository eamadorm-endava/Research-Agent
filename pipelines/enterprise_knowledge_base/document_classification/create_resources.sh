#!/bin/bash
# create_resources.sh - Setup for Document Classification Pipeline Prototyping

set -e

PROJECT_ID=$(gcloud config get-value project)
BUCKET_NAME="ag-core-dev-fdx7-kb-landing-zone"
LOCATION="us-central1"

echo "Enabling required APIs..."
gcloud services enable dlp.googleapis.com storage.googleapis.com aiplatform.googleapis.com --project="${PROJECT_ID}"

echo "Creating landing zone bucket: ${BUCKET_NAME}..."
if gsutil ls -b "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
    echo "Bucket gs://${BUCKET_NAME} already exists."
else
    gcloud storage buckets create "gs://${BUCKET_NAME}" --location="${LOCATION}" --project="${PROJECT_ID}"
    echo "Bucket created."
fi

echo "Creating subdirectories..."
# Creating 0-byte objects to represent folders
echo -n "" | gcloud storage cp - "gs://${BUCKET_NAME}/ingested/"
echo -n "" | gcloud storage cp - "gs://${BUCKET_NAME}/processed/"

echo "Infrastructure setup complete."
