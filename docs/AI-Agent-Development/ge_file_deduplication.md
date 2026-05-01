# Gemini Enterprise File Deduplication

## Overview
This module implements a deduplication strategy for files uploaded through the Gemini Enterprise (GE) UI. GE UI often repeats previous attachments in subsequent messages of a conversation (Context Dumping), which can lead to redundant file storage and increased costs.

## Strategy
This module implements a **dual-layer deduplication strategy** to handle the various ways Gemini Enterprise (GE) UI transmits attachments:

1.  **Plugin Layer (`GeminiEnterpriseFileIngestionPlugin`)**:
    *   Acts as the primary guard during message interception.
    *   Handles both `inline_data` and GE text-extraction blocks (`<start_of_user_uploaded_file>`).
    *   Resolves the filename and compares the incoming data size with the existing artifact metadata.
    *   If a match is found, it immediately reuses the GCS reference, avoiding any downstream service calls.

2.  **Service Layer (`StorageService`)**:
    *   Acts as a centralized safety net within `save_artifact`.
    *   Performs a secondary name and size check before committing any write to GCS.
    *   If a duplicate is detected, it returns the existing version number instead of creating a new one.

## Components

### `StorageService`
- **Location**: `agent/core_agent/artifact_management/service.py`
- **Changes**: 
    *   Updated `get_artifact_metadata` to include `size` and `version`.
    *   Overrode `save_artifact` to implement the centralized deduplication check.

### `GeminiEnterpriseFileIngestionPlugin`
- **Location**: `agent/core_agent/plugins/ingestion/plugin.py`
- **Changes**: 
    *   Added deduplication guard in `_process_file_part` (for `inline_data`).
    *   Enhanced `_process_ge_text_match` with size validation for text-extracted blocks.

## Verification
Verification is performed via logs. When a deduplication event occurs, the following log is emitted:
`INFO: Deduplication: Skipping redundant GE upload for '{filename}' (Size: {size} bytes). Using existing GCS reference.`
