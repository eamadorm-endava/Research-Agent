# GCS Ingestion (V2)

## Overview
The GCS MCP has been upgraded to support a secure, identity-aware artifact ingestion pipeline. The core `upload_object` tool now focuses on GCS-to-GCS transfers, facilitating the movement of files from the initial agent landing zone to either the Enterprise Knowledge Base or personal user buckets.

## Key Features
- **Identity Injection**: Automatically extracts the user's email from the OAuth token and injects it as the `uploader` metadata on every transferred object.
- **Credential Switching**:
  - Uses **Service Account (SA)** credentials for transfers into the `kb-landing-zone` (Knowledge Base).
  - Uses **User OAuth** credentials for transfers into personal buckets.
- **ACL Bridge**: Supports reading files from `ai_agent_landing_zone` where users have been granted per-object access.

## Tool: `upload_object` (V2)

### Parameters
- `source_uri` (Required): The full `gs://` URI of the source file.
- `destination_bucket` (Required): The name of the target bucket.
- `path_inside_destination_bucket` (Optional): A folder prefix within the destination bucket.
- `name_of_the_file` (Optional): A new filename (without extension). The extension from the source is preserved.
- `metadata` (Optional): Custom key-value pairs. Note that `uploader` is always overwritten by the system.

### Workflow Example
1. User uploads `report.pdf` to the Gemini UI.
2. The agent persists it to `gs://ai_agent_landing_zone/.../report.pdf` and grants the user `OWNER` ACL.
3. User asks: "Store this in the knowledge base."
4. The agent calls `upload_object(source_uri="gs://ai_agent_landing_zone/...", destination_bucket="kb-landing-zone", ...)`.
5. The MCP detects the KB bucket, switches to **SA credentials**, copies the file, and sets `uploader: user@example.com`.

## Configuration
The following environment variables control the ingestion logic:
- `AI_AGENT_LANDING_ZONE`: The source bucket for initial uploads.
- `KB_LANDING_ZONE`: The internal destination bucket for ingestion.

## Technical Details
- **Implementation**: `mcp_servers/gcs/app/mcp_server.py`
- **Client Logic**: `mcp_servers/gcs/app/gcs_client.py`
- **Schemas**: `mcp_servers/gcs/app/schemas.py`
