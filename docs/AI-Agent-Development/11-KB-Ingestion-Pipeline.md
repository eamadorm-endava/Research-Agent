# KB Ingestion Module

The `kb_ingestion` module provides the logic and tools necessary to ingest user-uploaded documents into the Enterprise Knowledge Base (EKB).

## Components

### 1. `TriggerEKBPipelineTool`
- **Location**: `agent/core_agent/tools/kb_tools.py`
- **Description**: Triggers the downstream EKB Cloud Run ingestion pipeline.
- **Authentication**: Uses Google OIDC ID tokens for service-to-service authentication.
- **Input**: `gcs_uri` (the canonical path in `kb-landing-zone`).

### 2. `kb-file-ingestion` Skill
- **Location**: `agent/skills/kb-file-ingestion/SKILL.md`
- **Description**: A multi-turn ADK skill that orchestrates the entire ingestion lifecycle:
    - Discovery of session artifacts.
    - Project deduplication and similarity checking via BigQuery.
    - Filename collision detection.
    - Metadata enrichment (Domain, Trust Level, PII status).
    - File relocation to the KB landing zone bucket.
    - Metadata stamping on GCS objects.
    - Triggering the EKB pipeline.

## Configuration
The module relies on the following environment variables:
- `EKB_PIPELINE_URL`: The base URL of the Cloud Run service.
- `GCS_KB_INGESTION_BUCKET`: (Usually `kb-landing-zone`) where documents are moved before ingestion.

## Workflow
1. User requests ingestion.
2. Skill collects metadata and validates against BigQuery.
3. Skill moves the file from `ai_agent_landing_zone` to `kb-landing-zone`.
4. Skill stamps metadata on the destination object.
5. Tool triggers the `/ingest` endpoint on the EKB Pipeline.

## Proactive Notification System
The agent core includes a **`sync_ingestion_status`** callback that enhances the user experience by providing real-time updates on background jobs.

- **Hook**: `before_agent_callback`.
- **Logic**:
    - Checks the session state for pending `job_id`s.
    - Synchronizes status with the EKB Pipeline `/status` endpoint.
    - If a job is finished, it injects a **System Update** event into the conversation history using the ADK 2.0 `session.events` pattern.
- **Benefit**: The agent "notices" when a document is ready for use right before responding to the user, even if the user didn't explicitly ask for a status update.
