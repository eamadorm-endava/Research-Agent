# SharePoint MCP Server

Read-only Model Context Protocol server for Microsoft SharePoint and OneDrive for Business document libraries through Microsoft Graph.

## Purpose

This connector lets the Research Agent discover SharePoint sites, list document libraries, inspect files and folders, and copy a selected SharePoint file into the managed ADK/Gemini landing-zone bucket for native multimodal injection.

The SharePoint side is read-only. The only write operation performed by this server is the required internal copy into the configured GCS Landing Zone when `ingest_sharepoint_drive_item` is called.

## Tools

| Tool | Description | SharePoint mutation |
| --- | --- | --- |
| `search_sharepoint_sites` | Search sites visible to the signed-in user. | No |
| `list_sharepoint_site_drives` | List document-library drives in a site. | No |
| `list_sharepoint_drive_items` | List children from the root, a folder item ID, or a folder path. | No |
| `get_sharepoint_drive_item` | Read metadata for a single file or folder. | No |
| `search_sharepoint_drive_items` | Search files and folders within a document library drive. | No |
| `ingest_sharepoint_drive_item` | Download a file from Graph and stream it to the internal GCS Landing Zone. | No |

## Required Microsoft Graph delegated scopes

Configure the Microsoft Entra application with delegated permissions:

- `User.Read.All`
- `Files.Read.All`
- `Sites.Read.All`
- `offline_access` for refresh-token support in the OAuth connection manager

The token verifier checks the delegated token scopes and validates the token by calling Microsoft Graph `/me` before FastMCP runs any tool. Agent-side Microsoft OAuth variables are intentionally Microsoft-wide, for example `GEMINI_MICROSOFT_AUTH_ID` and `MICROSOFT_GRAPH_OAUTH_SCOPES`, so the same delegated Microsoft authorization can be reused by future Microsoft MCP servers.

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `MICROSOFT_TENANT_ID` | `organizations` | Tenant ID or Microsoft tenant alias used in the issuer URL. Legacy fallback: `SHAREPOINT_TENANT_ID`. |
| `SHAREPOINT_LANDING_ZONE_BUCKET` | Falls back to `LANDING_ZONE_BUCKET`, then `GCS_LANDING_ZONE_BUCKET`, then mock bucket | GCS bucket used for file injection copies. |

The server uses Application Default Credentials for GCS landing-zone writes and IAM policy updates. Do not use JSON credential files.

## Local run

From the repository root:

```bash
make run-sharepoint-mcp-locally
```

By default the server listens on port `8084` through the Make target.

## Tests

```bash
make run-sharepoint-tests
```

## Docker build

```bash
make build-sharepoint-mcp-image
```

## File ingestion behavior

`ingest_sharepoint_drive_item` follows the repository MCP landing-zone standard:

```text
gs://{LANDING_ZONE_BUCKET}/<app_name>/<user_id>/<session_id>/sharepoint-<UTC timestamp>-<filename>
```

The response returns:

- `gcs_uri`
- `mime_type`
- `inject_file_data: true`

This lets the `MultimodalFileInjectionPlugin` load the file natively into the agent context without exposing raw file bytes in a tool response.
