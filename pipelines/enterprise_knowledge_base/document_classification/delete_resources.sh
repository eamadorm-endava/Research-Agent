#!/bin/bash
# delete_resources.sh - Cleanup for Document Classification Pipeline Prototyping

set -e

BUCKET_NAME="ag-core-dev-fdx7-kb-landing-zone"

echo "Deleting landing zone bucket and its contents: ${BUCKET_NAME}..."
if gsutil ls -b "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
    gcloud storage rm -r "gs://${BUCKET_NAME}" --quiet
    echo "Landing bucket deleted."
fi

echo "Deleting domain buckets..."
DOMAINS=("it" "finance" "hr" "sales" "executives" "legal" "operations")
for domain in "${DOMAINS[@]}"; do
    BUCKET="kb-${domain}"
    if gsutil ls -b "gs://${BUCKET}" >/dev/null 2>&1; then
        gcloud storage rm -r "gs://${BUCKET}" --quiet
        echo "Bucket gs://${BUCKET} deleted."
    fi
done

echo "Deleting BigQuery dataset..."
DATASET_NAME="knowledge_base"
if bq show "knowledge_base" >/dev/null 2>&1; then
    bq rm -r -f -d "knowledge_base"
    echo "Dataset deleted."
fi

echo "Infrastructure cleanup complete."
