# GCS MCP Ingestion Module

The GCS MCP Ingestion module provides a secure, identity-aware pipeline for moving objects between Google Cloud Storage buckets. It is designed to handle both user-delegated operations and automated internal ingestion pipelines.

## 1. URI-Based Ingestion

The module replaces direct byte uploads with a GCS-to-GCS model. This ensures that the MCP server never handles raw data, reducing security risks and improving performance for large files.

### 1.1 Tool: `upload_object`

**Parameters:**
- `source_gcs_uri`: The source object URI (e.g., `gs://source-bucket/path/to/file.zip`).
- `destination_bucket`: The target bucket name.
- `filename`: The new name for the object in the destination.
- `path_inside_bucket` (Optional): The folder path in the destination bucket.

## 2. Authentication Strategy

The module implements a **Conditional Authentication Gate** to balance security and automation.

### 2.1 Service Account (SA) Flow
Used exclusively for moves from the **Landing Zone** to the **Knowledge Base**.
- **Source**: `ai_agent_landing_zone`
- **Destination**: `kb-landing-zone`
- **Credential**: Uses the Cloud Run instance's Service Account. This allows the agent to trigger ingestion without requiring the user to have direct write access to the KB.

### 2.2 OAuth Flow
Used for all other operations (e.g., user-to-user bucket moves).
- **Credential**: Uses the user's delegated OAuth token.
- **Permission**: The user must have `storage.objects.get` on the source and `storage.objects.create` on the destination.

## 3. Configuration

The module uses environment variables to identify the protected ingestion zones:
- `GCS_LANDING_ZONE_BUCKET`: Defaults to `ai_agent_landing_zone`.
- `GCS_KB_INGESTION_BUCKET`: Defaults to `kb-landing-zone`.

## 4. Metadata Preservation

All metadata, including `Content-Type` and custom user metadata, is preserved during the copy operation.
