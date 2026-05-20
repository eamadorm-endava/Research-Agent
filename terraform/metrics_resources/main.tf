variable "project_id" {
  type        = string
  description = "The GCP project ID"
  default     = "ag-core-ops-auj0"
}

variable "main_region" {
  type        = string
  description = "The main GCP region"
  default     = "us-central1"
}

variable "bq_dataset_id" {
  type        = string
  description = "The BigQuery dataset ID for metrics logging"
  default     = "agent_metrics"
}

variable "bq_table_id" {
  type        = string
  description = "The BigQuery table ID for response time metrics"
  default     = "response_times"
}

resource "google_bigquery_dataset" "metrics" {
  project                    = var.project_id
  dataset_id                 = var.bq_dataset_id
  friendly_name              = "agent_metrics"
  description                = "Dataset to collect agent and tool response time metrics"
  location                   = var.main_region
  delete_contents_on_destroy = true
}

resource "google_bigquery_table" "response_times" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.metrics.dataset_id
  table_id            = var.bq_table_id
  deletion_protection = false

  schema = <<EOF
[
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
]
EOF
}
