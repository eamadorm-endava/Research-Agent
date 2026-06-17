# SharePoint MCP Server

Read-only Model Context Protocol server for Microsoft SharePoint and OneDrive for Business document libraries through Microsoft Graph.

## Purpose

This connector lets the Research Agent discover SharePoint sites, inspect site metadata, list document libraries, lists, pages, files, and folders, read structured site/list/page content, and copy selected SharePoint files into the managed ADK/Gemini landing-zone bucket for native multimodal injection.

The SharePoint side is read-only. The only write operation performed by this server is the required internal copy into the configured GCS Landing Zone when `ingest_sharepoint_drive_item` is called.

## Tools

| Tool | Description | SharePoint mutation |
| --- | --- | --- |
| `search_sharepoint_sites` | Search sites visible to the signed-in user. | No |
| `get_sharepoint_site` | Read expanded site metadata and description. | No |
| `discover_sharepoint_site_content` | Return a site overview containing metadata, libraries, lists, and pages. | No |
| `list_sharepoint_site_drives` | List document-library drives in a site. | No |
| `list_sharepoint_site_lists` | List SharePoint lists in a site. | No |
| `list_sharepoint_list_items` | Read visible field values from a SharePoint list. | No |
| `list_sharepoint_site_pages` | List modern SharePoint pages in a site. | No |
| `get_sharepoint_site_page` | Read metadata and best-effort text from a modern SharePoint page. | No |
| `list_sharepoint_drive_items` | List children from the root, a folder item ID, or a folder path. | No |
| `get_sharepoint_drive_item` | Read metadata for a single file or folder. | No |
| `search_sharepoint_drive_items` | Search files and folders within a document library drive. | No |
| `ingest_sharepoint_drive_item` | Download a file from Graph and stream it to the internal GCS Landing Zone. | No |

## Required Microsoft Graph delegated scopes

Configure the Microsoft Entra application with delegated permissions:

- `User.Read`
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

Site pages and list items are returned as structured text/metadata because they are not binary files. Office documents, PDFs, images, and other SharePoint drive items are not parsed inside the MCP server; they are copied into the landing zone so the agent/model can interpret them natively.

The response returns:

- `gcs_uri`
- `mime_type`
- `inject_file_data: true`

This lets the `MultimodalFileInjectionPlugin` load the file natively into the agent context without exposing raw file bytes in a tool response.
