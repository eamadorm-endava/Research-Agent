# Gemini Enterprise File Deduplication

## Overview
This module implements a deduplication strategy for files uploaded through the Gemini Enterprise (GE) UI. GE UI often repeats previous attachments in subsequent messages of a conversation (Context Dumping), which can lead to redundant file storage and increased costs.

## Strategy
The deduplication logic is integrated into the `GeminiEnterpriseFileIngestionPlugin`. For each `inline_data` part in a user message, the plugin:
1.  **Resolves the filename**: Uses the `display_name` from the `inline_data` or a generated name.
2.  **Checks existing metadata**: Queries the `StorageService` for any existing artifacts with the same name in the current session.
3.  **Compares size**: If an artifact exists, it compares the size of the incoming binary data with the stored size.
4.  **Skips redundant uploads**: If both name and size match exactly, the plugin skips the GCS save operation and reuses the existing GCS URI.

## Components

### `StorageService`
- **Location**: `agent/core_agent/artifact_management/service.py`
- **Change**: Updated `get_artifact_metadata` to include the `size` of the latest artifact version.

### `GeminiEnterpriseFileIngestionPlugin`
- **Location**: `agent/core_agent/plugins/ingestion/plugin.py`
- **Change**: Added a guard clause in `_process_file_part` to perform the name and size comparison before calling `save_artifact`.

## Verification
Verification is performed via logs. When a deduplication event occurs, the following log is emitted:
`INFO: Deduplication: Skipping redundant GE upload for '{filename}' (Size: {size} bytes). Using existing GCS reference.`
