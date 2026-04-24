#!/bin/bash
set -e

PROJECT_ID=$1
LOCATION="us-central1"
DATASET="knowledge_base"
CONNECTION_NAME="vertex_ai_connection"

if [ -z "$PROJECT_ID" ]; then
  echo "Usage: $0 <project_id>"
  exit 1
fi

echo "Provisioning BigQuery Cloud Resource connection..."
bq mk --connection --location=$LOCATION --project_id=$PROJECT_ID --connection_type=CLOUD_RESOURCE $CONNECTION_NAME || true

echo "Extracting service account and granting Vertex AI User role..."
SA_EMAIL=$(bq show --format=json --connection $PROJECT_ID.$LOCATION.$CONNECTION_NAME | jq -r '.cloudResource.serviceAccountId')
echo "Service Account: $SA_EMAIL"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/aiplatform.user" \
  --condition=None

echo "Sleeping for 15 seconds to allow IAM propagation..."
sleep 15

echo "Creating BigQuery remote model knowledge_base.multimodal_embedding_model..."
bq query --use_legacy_sql=false \
"CREATE OR REPLACE MODEL \`$PROJECT_ID.$DATASET.multimodal_embedding_model\`
REMOTE WITH CONNECTION \`$PROJECT_ID.$LOCATION.$CONNECTION_NAME\`
OPTIONS(ENDPOINT = 'multimodalembedding@001');"

echo "Creating BigQuery table knowledge_base.documents_metadata..."
bq query --use_legacy_sql=false \
"CREATE TABLE IF NOT EXISTS \`$PROJECT_ID.$DATASET.documents_metadata\` (
  document_id STRING,
  gcs_uri STRING,
  filename STRING,
  classification_tier INT64,
  domain STRING,
  confidence_score FLOAT64,
  trust_level STRING,
  project_id STRING,
  uploader_email STRING,
  description STRING,
  version INT64,
  is_latest BOOL,
  ingested_at TIMESTAMP
);"

echo "Resources created successfully."
