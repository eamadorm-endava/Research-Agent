#!/bin/bash
# Script to manually create BigQuery dataset and table for response time metrics.

PROJECT_ID="ag-core-ops-auj0"
DATASET_ID="agent_metrics"
TABLE_ID="response_times"
LOCATION="us-central1"

echo "Creating BigQuery dataset ${DATASET_ID} in project ${PROJECT_ID}..."
bq mk --project_id "${PROJECT_ID}" --location "${LOCATION}" --dataset "${DATASET_ID}" 2>/dev/null || echo "Dataset may already exist."

echo "Creating BigQuery table ${DATASET_ID}.${TABLE_ID}..."

SCHEMA='[
  {"name": "session_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique identifier for the session"},
  {"name": "user_id", "type": "STRING", "mode": "NULLABLE", "description": "Identifier for the user"},
  {"name": "prompt_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique identifier for the prompt invocation"},
  {"name": "prompt", "type": "STRING", "mode": "NULLABLE", "description": "Text content of the user prompt"},
  {"name": "agent_response", "type": "STRING", "mode": "NULLABLE", "description": "Text content of the agent response"},
  {"name": "initial_time", "type": "TIMESTAMP", "mode": "REQUIRED", "description": "Timestamp when the prompt was received"},
  {"name": "final_time", "type": "TIMESTAMP", "mode": "REQUIRED", "description": "Timestamp when the response was returned"},
  {"name": "time_to_answer", "type": "FLOAT", "mode": "REQUIRED", "description": "Total processing time in seconds"},
  {
    "name": "tools_used",
    "type": "RECORD",
    "mode": "REPEATED",
    "description": "List of tools invoked during the turn",
    "fields": [
      {"name": "tool_name", "type": "STRING", "mode": "REQUIRED", "description": "Name of the tool executed"},
      {"name": "initial_time", "type": "TIMESTAMP", "mode": "REQUIRED", "description": "Timestamp when the tool started executing"},
      {"name": "final_time", "type": "TIMESTAMP", "mode": "REQUIRED", "description": "Timestamp when the tool completed executing"},
      {"name": "tool_full_time", "type": "FLOAT", "mode": "REQUIRED", "description": "Duration of tool execution in seconds"}
    ]
  }
]'

# Write schema temporarily to pass to bq mk
echo "${SCHEMA}" > /tmp/metrics_schema.json

bq mk --project_id "${PROJECT_ID}" \
      --table \
      --description "Agent execution and tool response metrics" \
      "${DATASET_ID}.${TABLE_ID}" \
      /tmp/metrics_schema.json

rm -f /tmp/metrics_schema.json

echo "BigQuery resources initialized successfully."
