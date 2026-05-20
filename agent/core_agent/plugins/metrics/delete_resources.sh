#!/bin/bash
# Script to manually clean up BigQuery dataset and table for response time metrics.

PROJECT_ID="ag-core-ops-auj0"
DATASET_ID="agent_metrics"
TABLE_ID="response_times"

echo "Deleting BigQuery table ${PROJECT_ID}:${DATASET_ID}.${TABLE_ID}..."
bq rm -f --project_id "${PROJECT_ID}" --table "${DATASET_ID}.${TABLE_ID}"

echo "Deleting BigQuery dataset ${PROJECT_ID}:${DATASET_ID}..."
bq rm -f -r --project_id "${PROJECT_ID}" --dataset "${DATASET_ID}"

echo "BigQuery resources cleaned up successfully."
