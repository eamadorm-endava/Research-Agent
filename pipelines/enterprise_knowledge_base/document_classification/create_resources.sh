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
    echo "Creating table with REQUIRED schema..."
    
    # Create temporary schema file
    cat <<EOF > schema.json
[
  {"name": "document_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "gcs_uri", "type": "STRING", "mode": "REQUIRED"},
  {"name": "filename", "type": "STRING", "mode": "REQUIRED"},
  {"name": "classification_tier", "type": "STRING", "mode": "REQUIRED"},
  {"name": "domain", "type": "STRING", "mode": "REQUIRED"},
  {"name": "confidence_score", "type": "FLOAT64", "mode": "REQUIRED"},
  {"name": "trust_level", "type": "STRING", "mode": "REQUIRED"},
  {"name": "project_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "uploader_email", "type": "STRING", "mode": "REQUIRED"},
  {"name": "description", "type": "STRING", "mode": "REQUIRED"},
  {"name": "version", "type": "INT64", "mode": "REQUIRED"},
  {"name": "latest", "type": "BOOL", "mode": "REQUIRED"},
  {"name": "ingested_at", "type": "TIMESTAMP", "mode": "REQUIRED"}
]
EOF

    bq mk --table "${PROJECT_ID}:${DATASET_NAME}.${TABLE_NAME}" schema.json
    rm schema.json
    echo "Table created."
fi

echo "Infrastructure setup complete."
