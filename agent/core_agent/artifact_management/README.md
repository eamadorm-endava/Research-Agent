# Artifact Management

This module handles the lifecycle, persistence, and security of ADK Session Artifacts in Google Cloud Storage (GCS).

## Responsibilities

1.  **Persistence**: Saving and loading artifacts from the application's GCS bucket.
2.  **MIME Type Resolution**: Ensuring all artifacts have valid MIME types (Gemini does not support `application/octet-stream`).
3.  **Identity-Aware Security**: Applying IAM binding conditions at the folder level to ensure users only have access to their own artifacts.
4.  **Zero-Copy References**: Returning `file_data` Parts with `gs://` URIs instead of binary payloads to save tokens and improve performance.

## Key Components

- **`StorageService`**: An implementation of `google.adk.artifacts.GcsArtifactService` tailored for Gemini Enterprise requirements.

## Usage

The `StorageService` is registered in the `AdkApp` via the `AppBuilder`:

```python
AdkApp(
    app=base_application,
    artifact_service_builder=lambda: StorageService(bucket_name=bucket_name),
)
```
