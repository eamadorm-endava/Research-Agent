# Storage Module

This module provides a unified interface for artifact persistence and identity-aware security.

## StorageService

The `StorageService` extends the ADK `GcsArtifactService` to provide enterprise-grade features:

1.  **Reference-Based Loading**: Automatically converts binary parts into `file_data` URIs (`gs://...`). This is crucial for Gemini Enterprise, as it prevents request payload bloat and allows Gemini to resolve the file directly from GCS.
2.  **MIME Type Discovery**: Automatically resolves the correct MIME type from GCS blob metadata, ensuring compatibility with Vertex AI ingestion.
3.  **Identity-Aware Security**: Implements folder-level IAM binding conditions. Instead of individual object ACLs, it uses a Common Expression Language (CEL) condition to grant `roles/storage.objectAdmin` to the uploader over their specific `app_name/user_email/` directory.
4.  **Lazy Association**: Provides `get_artifact_metadata` to allow other modules (like the Ingestion Plugin) to discover files that were "pre-stashed" in GCS by Gemini Enterprise.

## Security Model

The service enforces **Uniform Bucket-Level Access (UBLA)**. Permissions are isolated at the folder level, ensuring that users can only access their own uploaded files.

```python
# Example Usage
await storage_service.save_artifact(
    app_name="core_agent",
    user_id="user@example.com",
    filename="report.pdf",
    artifact=part
)
```
