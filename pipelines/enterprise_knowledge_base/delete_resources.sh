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

echo "Deleting BigQuery remote model knowledge_base.multimodal_embedding_model..."
bq query --use_legacy_sql=false "DROP MODEL IF EXISTS \`$PROJECT_ID.$DATASET.multimodal_embedding_model\`;"

echo "Deleting BigQuery Cloud Resource connection..."
bq rm --connection --location=$LOCATION --project_id=$PROJECT_ID $CONNECTION_NAME || true

echo "Deleting BigQuery table knowledge_base.documents_metadata..."
bq query --use_legacy_sql=false "DROP TABLE IF EXISTS \`$PROJECT_ID.$DATASET.documents_metadata\`;"

echo "Resources deleted successfully."
