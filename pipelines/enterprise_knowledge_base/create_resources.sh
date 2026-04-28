#!/bin/bash
# create_resources.sh - Unified Infrastructure Setup for EKB Pipeline
set -e

PROJECT_ID=$1
LOCATION="us-central1"
DATASET="knowledge_base"
CONNECTION_NAME="vertex_ai_connection"

if [ -z "$PROJECT_ID" ]; then
  echo "Usage: $0 <project_id>"
  exit 1
fi

echo "--------------------------------------------------------"
echo "1. Enabling Required APIs..."
echo "--------------------------------------------------------"
gcloud services enable \
  dlp.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  bigquery.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project="${PROJECT_ID}"

echo "--------------------------------------------------------"
echo "2. Creating GCS Buckets..."
echo "--------------------------------------------------------"
BUCKETS=(
  "${PROJECT_ID}-kb-landing-zone"
  "${PROJECT_ID}-rag-staging"
  "${PROJECT_ID}-kb-it"
  "${PROJECT_ID}-kb-finance"
  "${PROJECT_ID}-kb-hr"
  "${PROJECT_ID}-kb-legal"
  "${PROJECT_ID}-kb-operations"
  "${PROJECT_ID}-kb-sales"
  "${PROJECT_ID}-kb-executives"
)

for BUCKET in "${BUCKETS[@]}"; do
  if gsutil ls -b "gs://${BUCKET}" >/dev/null 2>&1; then
    echo "Bucket gs://${BUCKET} already exists."
  else
    echo "Creating bucket: gs://${BUCKET}..."
    gcloud storage buckets create "gs://${BUCKET}" --location="${LOCATION}" --project="${PROJECT_ID}"
  fi
done

echo "Initializing landing zone subdirectories..."
echo -n "" | gcloud storage cp - "gs://${PROJECT_ID}-kb-landing-zone/ingested/"

echo "--------------------------------------------------------"
echo "3. Setting up BigQuery Connection & ML Models..."
echo "--------------------------------------------------------"
echo "Creating BigQuery Dataset: ${DATASET}..."
bq mk --dataset --location=$LOCATION $PROJECT_ID:$DATASET || true

echo "Provisioning BigQuery Cloud Resource connection..."
bq mk --connection --location=$LOCATION --project_id=$PROJECT_ID --connection_type=CLOUD_RESOURCE $CONNECTION_NAME || true

echo "Extracting service account and granting Vertex AI User role..."
SA_EMAIL=$(bq show --format=json --connection $PROJECT_ID.$LOCATION.$CONNECTION_NAME | jq -r '.cloudResource.serviceAccountId')
echo "BigQuery Connection Service Account: $SA_EMAIL"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/aiplatform.user" \
  --condition=None

echo "Sleeping for 10 seconds to allow IAM propagation..."
sleep 10

echo "Creating BigQuery remote model: multimodal_embedding_model..."
bq query --use_legacy_sql=false \
"CREATE OR REPLACE MODEL \`$PROJECT_ID.$DATASET.multimodal_embedding_model\`
REMOTE WITH CONNECTION \`$PROJECT_ID.$LOCATION.$CONNECTION_NAME\`
OPTIONS(ENDPOINT = 'multimodalembedding@001');"

echo "--------------------------------------------------------"
echo "4. Creating BigQuery Tables (JSON Schemas)..."
echo "--------------------------------------------------------"

# 4.1 Metadata Table Schema
cat <<EOF > metadata_schema.json
[
  {"name": "document_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique UUID for the document"},
  {"name": "gcs_uri", "type": "STRING", "mode": "REQUIRED", "description": "Final GCS URI in the domain bucket"},
  {"name": "filename", "type": "STRING", "mode": "REQUIRED", "description": "The original filename"},
  {"name": "classification_tier", "type": "STRING", "mode": "NULLABLE", "description": "Security tier label"},
  {"name": "domain", "type": "STRING", "mode": "NULLABLE", "description": "Business domain"},
  {"name": "confidence_score", "type": "FLOAT64", "mode": "NULLABLE", "description": "Classification confidence"},
  {"name": "trust_level", "type": "STRING", "mode": "NULLABLE", "description": "Document trust maturity"},
  {"name": "project_id", "type": "STRING", "mode": "NULLABLE", "description": "Associated project ID"},
  {"name": "uploader_email", "type": "STRING", "mode": "NULLABLE", "description": "Uploader email address"},
  {"name": "description", "type": "STRING", "mode": "NULLABLE", "description": "AI-generated summary"},
  {"name": "version", "type": "INT64", "mode": "NULLABLE", "description": "Incremental version number"},
  {"name": "latest", "type": "BOOL", "mode": "NULLABLE", "description": "Latest version flag"},
  {"name": "ingested_at", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "ISO timestamp of ingestion"}
]
EOF

echo "Creating table: documents_metadata..."
if bq show "$PROJECT_ID:$DATASET.documents_metadata" >/dev/null 2>&1; then
    echo "Table documents_metadata already exists."
else
    bq mk --table \
       --description "Storage for document classification and routing metadata" \
       "$PROJECT_ID:$DATASET.documents_metadata" metadata_schema.json
fi

# 4.2 Chunks Table Schema
cat <<EOF > chunks_schema.json
[
  {"name": "chunk_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique UUID for the chunk"},
  {"name": "document_id", "type": "STRING", "mode": "REQUIRED", "description": "Parent document UUID"},
  {"name": "chunk_data", "type": "STRING", "mode": "NULLABLE", "description": "Text content of the chunk"},
  {"name": "gcs_uri", "type": "STRING", "mode": "NULLABLE", "description": "Original GCS URI (Domain)"},
  {"name": "filename", "type": "STRING", "mode": "NULLABLE", "description": "Source filename"},
  {"name": "structural_metadata", "type": "STRING", "mode": "NULLABLE", "description": "JSON metadata (page, etc.)"},
  {"name": "page_number", "type": "INT64", "mode": "NULLABLE", "description": "Source page number"},
  {"name": "embedding", "type": "FLOAT64", "mode": "REPEATED", "description": "Semantic vector embedding"},
  {"name": "created_at", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "Creation timestamp"},
  {"name": "vectorized_at", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "Vectorization timestamp"}
]
EOF

echo "Creating table: documents_chunks..."
if bq show "$PROJECT_ID:$DATASET.documents_chunks" >/dev/null 2>&1; then
    echo "Table documents_chunks already exists."
else
    bq mk --table \
       --description "Storage for document chunks and vector embeddings" \
       "$PROJECT_ID:$DATASET.documents_chunks" chunks_schema.json
fi

# Cleanup temporary schema files
rm metadata_schema.json chunks_schema.json

echo "--------------------------------------------------------"
echo "Infrastructure Setup Complete!"
echo "--------------------------------------------------------"
