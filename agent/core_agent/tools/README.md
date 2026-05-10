# Agent Tools

This module contains standalone ADK tools that are explicitly registered with agents to provide specific capabilities.

## Tools Overview

### `artifact_tools.py`
- **`GetArtifactUriTool`**: Retrieves the canonical GCS URI for a file registered in the current session.
- **`ImportGcsToArtifactTool`**: Registers an external GCS object as an ADK session artifact for zero-copy analysis.

### `kb_tools.py`
- **`TriggerEKBPipelineTool`**: POSTs a GCS document URI to the EKB pipeline `/ingest` endpoint, stores the returned `job_id` in session state under `pending_ingestions`, and returns a user-friendly confirmation.
- **`CheckIngestionStatusTool`**: GETs the current status of a specific EKB ingestion job by `job_id` from the pipeline `/status/{job_id}` endpoint.

Both tools authenticate against the EKB Cloud Run service using a GCP OIDC identity token obtained at call time via the `security` module.

### `kb_schemas.py`
Pydantic `BaseModel` schemas used by `kb_tools.py`:
- **`TriggerEKBPipelineRequest`** / **`TriggerEKBPipelineResponse`** — input and output for the trigger tool.
- **`CheckIngestionStatusRequest`** / **`CheckIngestionStatusResponse`** — input and output for the status tool.

### `time_tools.py`
- **`GetCurrentTimeTool`**: Returns the current date and time in ISO 8601 format for the Central Time zone (America/Chicago). Used by the Research Specialist to anchor date calculations before calendar queries.

## Registration

Tools are registered per agent via `AgentBuilder.with_native_tools()`:

```python
# Research Specialist
agent_builder.with_native_tools([
    GetArtifactUriTool(),
    ImportGcsToArtifactTool(),
    GetCurrentTimeTool(),
    load_artifacts,
])

# Ingestion Specialist
agent_builder.with_native_tools([
    GetArtifactUriTool(),
    ImportGcsToArtifactTool(),
    TriggerEKBPipelineTool(),
    CheckIngestionStatusTool(),
    load_artifacts,
])

# Coordinator
agent_builder.with_native_tools([GetArtifactUriTool(), load_artifacts])
```

