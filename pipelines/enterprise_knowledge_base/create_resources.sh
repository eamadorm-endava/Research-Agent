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
    echo "Bucket gs://${BUCKET} already exists."
  else
    echo "Creating bucket: gs://${BUCKET}..."
    gcloud storage buckets create "gs://${BUCKET}" --location="${LOCATION}" --project="${PROJECT_ID}"
  fi
done


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
  {"name": "gcs_uri", "type": "STRING", "mode": "REQUIRED", "description": "Final GCS URI in the domain bucket (Original)"},
  {"name": "filename", "type": "STRING", "mode": "REQUIRED", "description": "The original filename"},
  {"name": "classification_tier", "type": "STRING", "mode": "REQUIRED", "description": "String classification label (public, confidential, etc.)"},
  {"name": "domain", "type": "STRING", "mode": "REQUIRED", "description": "The business domain (it, hr, etc.)"},
  {"name": "confidence_score", "type": "FLOAT64", "mode": "REQUIRED", "description": "AI classifier confidence (0.0 - 1.0)"},
  {"name": "trust_level", "type": "STRING", "mode": "REQUIRED", "description": "Trust maturity (published, wip, archived)"},
  {"name": "project_id", "type": "STRING", "mode": "REQUIRED", "description": "Project identifier"},
  {"name": "uploader_email", "type": "STRING", "mode": "REQUIRED", "description": "Uploader's email address"},
  {"name": "description", "type": "STRING", "mode": "REQUIRED", "description": "AI-generated content summary"},
  {"name": "version", "type": "INTEGER", "mode": "REQUIRED", "description": "Incremental version number"},
  {"name": "latest", "type": "BOOLEAN", "mode": "REQUIRED", "description": "Whether this is the latest version"},
  {"name": "ingested_at", "type": "TIMESTAMP", "mode": "REQUIRED", "description": "ISO 8601 ingestion timestamp"}
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
  {"name": "document_id", "type": "STRING", "mode": "REQUIRED", "description": "Deterministic UUID for the document"},
  {"name": "chunk_data", "type": "STRING", "mode": "REQUIRED", "description": "Text content of the chunk"},
  {"name": "gcs_uri", "type": "STRING", "mode": "REQUIRED", "description": "Original GCS URI of the document"},
  {"name": "filename", "type": "STRING", "mode": "REQUIRED", "description": "Basename of the file"},
  {"name": "structural_metadata", "type": "JSON", "mode": "REQUIRED", "description": "Structured page info, layout data, etc."},
  {"name": "page_number", "type": "INTEGER", "mode": "REQUIRED", "description": "Page number where the chunk was found"},
  {"name": "embedding", "type": "FLOAT64", "mode": "REPEATED", "description": "Vector embedding (empty initially)"},
  {"name": "created_at", "type": "TIMESTAMP", "mode": "REQUIRED", "description": "ISO timestamp of creation"},
  {"name": "vectorized_at", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "ISO timestamp of vectorization"}
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
