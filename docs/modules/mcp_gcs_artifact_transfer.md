# GCS Artifact Transfer Module

This module enables secure and auditable transfer of artifacts from the ADK agent runtime to the Enterprise Knowledge Base landing zone.

## Overview

The `upload_object` tool in the GCS MCP server serves as the bridge for artifact ingestion. It supports GCS-to-GCS transfers using `source_uri` and automatically injects user identity metadata extracted from OAuth tokens.

## Tool Contract: `upload_object`

### Request Parameters

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `source_uri` | `str` | Yes* | The GCS URI of the source artifact (e.g., `gs://agent-landing-zone/file.pdf`). |
| `destination_uri` | `str` | Yes* | The GCS destination path (e.g., `gs://kb-landing-zone/raw/` or `gs://kb-landing-zone/raw/renamed.pdf`). |
| `metadata` | `dict[str, str]` | No | Optional custom metadata tags to apply to the object. |
| `bucket_name` | `str` | No** | Target bucket name (alternative to `destination_uri`). |
| `object_name` | `str` | No** | Target object name (alternative to `destination_uri`). |

*\*Either `source_uri` or `content` must be provided. For artifact transfer, `source_uri` is required.*
*\*\*Required if `destination_uri` is not provided.*

### Identity Injection

The tool automatically injects the following metadata field:
- **`x-goog-meta-user-email`**: Extracted from the `Authorization: Bearer <token>` header using the Google OAuth2 V3 `tokeninfo` endpoint.

> [!IMPORTANT]
> If the user's email cannot be extracted from the token, the tool will return an `AuthenticationError`. This ensures all landing-zone objects have a traceable creator.

## Example Flow

1. **Agent identifies artifact**: `gs://research-agent-artifacts/123-abc.pdf`
2. **Agent calls tool**:
   ```json
   {
     "source_uri": "gs://research-agent-artifacts/123-abc.pdf",
     "destination_uri": "gs://kb-landing-zone/raw/",
     "metadata": {
       "doc-type": "research-paper"
     }
   }
   ```
3. **Resulting Object**: `gs://kb-landing-zone/raw/123-abc.pdf`
   - Metadata: `user-email: user@example.com`, `doc-type: research-paper"
