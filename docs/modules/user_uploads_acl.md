# User Uploads ACL Plugin

## Overview
The `GeminiEnterpriseFileIngestionPlugin` intercepts user-uploaded files from Gemini Enterprise, persists them to Google Cloud Storage (GCS), and replaces the binary payload with a GCS-backed reference. 

To ensure users can manage their own uploads, the plugin automatically grants the uploader `OWNER` level access (similar to Storage Object Admin) to the specific GCS object they uploaded.

## Architecture
When a file is uploaded:
1. The plugin saves the artifact using the `ArtifactService`.
2. It retrieves the canonical `gs://` URI.
3. It extracts the bucket and object name.
4. It uses the GCS Python SDK (via Service Account credentials) to update the object's ACL:
   ```python
   blob.acl.user(user_email).grant_owner()
   blob.acl.save()
   ```

## Security Considerations
- **Least Privilege**: The ACL is applied only to the specific object uploaded by the user, not the entire bucket.
- **Identity Trust**: The `user_email` is retrieved from the `InvocationContext`, which is populated by the ADK framework from the authenticated user's session.
- **UBLA Compatibility**: If the target bucket has **Uniform Bucket-Level Access (UBLA)** enabled, ACL operations will fail. The plugin logs this as a warning but does not block the upload, as the file is still successfully persisted and accessible to the agent.

## Implementation Details
- **Location**: `agent/core_agent/plugins/user_uploads.py`
- **Method**: `_grant_uploader_object_acl`
- **Error Handling**: Uses `asyncio.to_thread` for the synchronous GCS call and catches all exceptions to prevent ingestion failures if ACL granting fails.
