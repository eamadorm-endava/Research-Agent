# Plugins Module

This module contains lifecycle interceptors and post-turn callbacks that orchestrate the agent's behavior.

## User Uploads Ingestion

The `GeminiEnterpriseFileIngestionPlugin` is responsible for ensuring that any file uploaded by a user is correctly persisted and referenced.

### The Lifecycle
1.  **Interception**: The plugin hooks into `on_user_message_callback`.
2.  **Pre-Scan**: It scans the message for existing GCS references to populate a **Turn Registry**.
3.  **Inline Persistence**: It saves any raw `inline_data` bytes to GCS and replaces them with `file_data` references.
4.  **Tag Resolution (Discovery)**: It searches for GE tags (e.g., `<start_of_user_uploaded_file: ...>`). If the tags are empty, it uses the **Lazy Association** pattern to find the file in GCS (pre-stashed by Gemini Enterprise) and injects the correct `file_data` part.

## Artifact Rendering

The `storage/` sub-package contains the `render_pending_artifacts` callback.

- **Purpose**: Gemini Enterprise cannot render GCS URIs visually in the final response.
- **Mechanism**: This callback (registered as an `after_agent_callback`) scans the session state for pending artifacts, downloads them as bytes from the `StorageService`, and returns them as inline parts so they appear in the Gemini UI.
