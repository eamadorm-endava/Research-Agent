#!/bin/bash
# delete_resources.sh - Cleanup for Document Classification Pipeline Prototyping

set -e

BUCKET_NAME="enterprise_knowledgebase_landing_zone"

echo "Deleting landing zone bucket and its contents: ${BUCKET_NAME}..."
if gsutil ls -b "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
    gcloud storage rm -r "gs://${BUCKET_NAME}" --quiet
    echo "Bucket and contents deleted."
else
    echo "Bucket gs://${BUCKET_NAME} does not exist."
fi

echo "Infrastructure cleanup complete."
