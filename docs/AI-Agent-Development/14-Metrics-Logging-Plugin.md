# 14 - Metrics Logging Plugin

This document describes the design, schema, and usage of the `ResponseTimeMetricsPlugin`, which captures execution timestamps and durations for the agent turn and individual tool calls, logging them to BigQuery.

---

## 1. Architecture Overview

The `ResponseTimeMetricsPlugin` utilizes the Model Context Protocol / ADK plugin hooks to capture metrics without modifying the business logic of core agent capabilities:

1. **Start Precision**:
   - `before_run_callback` and `on_user_message_callback` are used to record the precise start time (`initial_time`) of the request and extract the text content of the user prompt.
2. **Tool Timing**:
   - `before_tool_callback` captures the initial timestamp of a tool call.
   - `after_tool_callback` (and `on_tool_error_callback`) calculate the elapsed duration (`tool_full_time`) and append the structured tool execution metric to the current run details.
3. **Flushing Metrics**:
   - `after_run_callback` performs the final calculations, computes the total `time_to_answer`, extracts the final text response of the root agent from the session event history, and writes the structured record to BigQuery using the streaming buffer.

---

## 2. BigQuery Table Schema

The tracking data is written to the table `ag-core-ops-auj0.agent_metrics.response_times` with the following schema:

| Field Name | Type | Mode | Description |
| :--- | :--- | :--- | :--- |
| `session_id` | STRING | REQUIRED | Unique identifier for the agent session |
| `user_id` | STRING | NULLABLE | Identifier for the user initiating the session |
| `prompt_id` | STRING | REQUIRED | Unique identifier for the turn invocation (prompt ID) |
| `prompt` | STRING | NULLABLE | Text content of the user prompt |
| `agent_response` | STRING | NULLABLE | Text content of the final agent response |
| `initial_time` | TIMESTAMP | REQUIRED | Timestamp when the user prompt was received |
| `final_time` | TIMESTAMP | REQUIRED | Timestamp when the final agent response was ready |
| `time_to_answer` | FLOAT | REQUIRED | Total time taken to process the turn in seconds |
| `tools_used` | RECORD | REPEATED | List of tools invoked during the agent turn |
| `tools_used.tool_name` | STRING | REQUIRED | The name of the tool that was executed |
| `tools_used.initial_time` | TIMESTAMP | REQUIRED | Timestamp when the tool started executing |
| `tools_used.final_time` | TIMESTAMP | REQUIRED | Timestamp when the tool completed executing |
| `tools_used.tool_full_time` | FLOAT | REQUIRED | Total duration of the tool execution in seconds |

---

## 3. Local Development vs. Production Execution

- **Lazy Client Initialization**: To prevent `DefaultCredentialsError` during configuration building in tests or local setups, the BigQuery client is loaded lazily on-demand.
- **Fail-Safe Design**: Errors during BigQuery operations (e.g. permission issues locally, connection drops) are caught silently and logged via `loguru` as `logger.error` or `logger.warning`, ensuring that the metrics tracking never interferes with the agent's response to the user.
- **Local credentials**: Local execution will utilize the developer's Application Default Credentials (ADC). Ensure your local environment is authenticated with a role that has permission to write to BigQuery:
  ```bash
  gcloud auth application-default login
  ```

---

## 4. Verification and Manual Resource Operations

Manual scripting is provided inside `agent/core_agent/plugins/metrics/` to provision and clean up prototyping tables:

- **Create resources manually**:
  ```bash
  bash agent/core_agent/plugins/metrics/create_resources.sh
  ```
- **Delete manual resources**:
  ```bash
  bash agent/core_agent/plugins/metrics/delete_resources.sh
  ```
