#!/bin/bash
# create_resources.sh - Setup for Document Classification Pipeline Prototyping

set -e

PROJECT_ID=$(gcloud config get-value project)
BUCKET_NAME="enterprise_knowledgebase_landing_zone"
LOCATION="us-central1"

echo "Enabling required APIs..."
gcloud services enable dlp.googleapis.com storage.googleapis.com aiplatform.googleapis.com bigquery.googleapis.com --project="${PROJECT_ID}"

echo "Creating landing zone bucket: ${BUCKET_NAME}..."
if gsutil ls -b "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
    echo "Bucket gs://${BUCKET_NAME} already exists."
else
    gcloud storage buckets create "gs://${BUCKET_NAME}" --location="${LOCATION}" --project="${PROJECT_ID}"
    echo "Bucket created."
fi

echo "Creating domain buckets..."
DOMAINS=("it" "finance" "hr" "sales" "executives" "legal" "operations")
for domain in "${DOMAINS[@]}"; do
    BUCKET="kb-${domain}"
    if gsutil ls -b "gs://${BUCKET}" >/dev/null 2>&1; then
        echo "Bucket gs://${BUCKET} already exists."
    else
        gcloud storage buckets create "gs://${BUCKET}" --location="${LOCATION}" --project="${PROJECT_ID}"
        echo "Bucket gs://${BUCKET} created."
    fi
done

echo "Creating BigQuery dataset and table..."
DATASET_NAME="knowledge_base"
TABLE_NAME="documents_metadata"

if bq show "${PROJECT_ID}:${DATASET_NAME}" >/dev/null 2>&1; then
    echo "Dataset ${DATASET_NAME} already exists."
else
    bq mk --dataset --location="${LOCATION}" "${PROJECT_ID}:${DATASET_NAME}"
    echo "Dataset created."
fi

if bq show "${PROJECT_ID}:${DATASET_NAME}.${TABLE_NAME}" >/dev/null 2>&1; then
    echo "Table ${TABLE_NAME} already exists."
else
    # Schema matches Design.md + Issue #114 requirements
    bq mk --table "${PROJECT_ID}:${DATASET_NAME}.${TABLE_NAME}" \
    document_id:STRING,gcs_uri:STRING,filename:STRING,classification_tier:INT64,domain:STRING,confidence_score:FLOAT64,trust_level:STRING,project_id:STRING,uploader_email:STRING,description:STRING,version:INT64,latest:BOOL,ingested_at:TIMESTAMP
    echo "Table created."
fi

echo "Infrastructure setup complete."
