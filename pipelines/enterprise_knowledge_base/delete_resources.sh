#!/bin/bash
# delete_resources.sh - Unified Infrastructure Teardown for EKB Pipeline
set -e

PROJECT_ID="ag-core-dev-fdx7"
LOCATION="us-central1"
DATASET="knowledge_base"
CONNECTION_NAME="vertex_ai_connection"

if [ -z "$PROJECT_ID" ]; then
  echo "Usage: $0 <project_id>"
  exit 1
fi

echo "--------------------------------------------------------"
echo "1. Deleting BigQuery Resources..."
echo "--------------------------------------------------------"
echo "Deleting remote model: multimodal_embedding_model..."
bq query --use_legacy_sql=false "DROP MODEL IF EXISTS \`$PROJECT_ID.$DATASET.multimodal_embedding_model\`;"

echo "Deleting table: documents_metadata..."
bq query --use_legacy_sql=false "DROP TABLE IF EXISTS \`$PROJECT_ID.$DATASET.documents_metadata\`;"

echo "Deleting table: documents_chunks..."
bq query --use_legacy_sql=false "DROP TABLE IF EXISTS \`$PROJECT_ID.$DATASET.documents_chunks\`;"

echo "Deleting BigQuery Dataset: ${DATASET}..."
bq rm -r -f -d $PROJECT_ID:$DATASET || true

echo "Deleting BigQuery Cloud Resource connection..."
bq rm --connection --location=$LOCATION --project_id=$PROJECT_ID $CONNECTION_NAME || true

echo "--------------------------------------------------------"
echo "2. Deleting GCS Buckets..."
echo "--------------------------------------------------------"
BUCKETS=(
  "${PROJECT_ID}-kb-landing-zone"
  "${PROJECT_ID}-rag-staging"
  "kb-it"
  "kb-finance"
  "kb-hr"
  "kb-legal"
  "kb-operations"
  "kb-sales"
  "kb-executives"
)

for BUCKET in "${BUCKETS[@]}"; do
  if gsutil ls -b "gs://${BUCKET}" >/dev/null 2>&1; then
    echo "Deleting bucket: gs://${BUCKET}..."
    gcloud storage buckets delete "gs://${BUCKET}" --project="${PROJECT_ID}" --quiet || true
  else
    echo "Bucket gs://${BUCKET} does not exist."
  fi
done

echo "--------------------------------------------------------"
echo "Infrastructure Teardown Complete!"
echo "--------------------------------------------------------"
