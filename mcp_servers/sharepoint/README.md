# SharePoint MCP Server

This directory contains the Model Context Protocol (MCP) server for integrating Microsoft SharePoint with the AI Agent through Microsoft Graph delegated authentication.

## Authentication

The SharePoint MCP follows the same delegated Microsoft OAuth pattern as the OneDrive MCP:

- Incoming MCP requests must include a Microsoft Entra access token.
- `MicrosoftTokenVerifier` validates the token by calling `https://graph.microsoft.com/v1.0/me`.
- Each tool creates a request-scoped `SharePointClient` from the validated token in the MCP auth context.
- Graph calls run with the signed-in user's permissions, so site and file visibility naturally follows that user's SharePoint access.

Required delegated Microsoft Graph scopes:

- `offline_access`
- `Files.Read.All`
- `Sites.Read.All`
- `User.Read` for token profile validation

## Tools

| Tool | What it does |
| --- | --- |
| `search_sharepoint_sites` | Searches SharePoint sites visible to the signed-in Microsoft user. |
| `get_sharepoint_site` | Reads expanded metadata for one SharePoint site. |
| `discover_sharepoint_site_content` | Returns site metadata, document libraries, lists, and modern pages in one call. |
| `list_sharepoint_site_drives` | Lists document-library drives available inside a site. |
| `list_sharepoint_site_lists` | Lists SharePoint lists inside a site. |
| `list_sharepoint_list_items` | Reads visible list item fields and builds compact previews. |
| `list_sharepoint_site_pages` | Lists modern SharePoint pages in a site. |
| `get_sharepoint_site_page` | Reads a modern page and extracts readable text from canvas/page payloads. |
| `list_sharepoint_drive_items` | Lists files and folders from a document-library root, folder item ID, or root-relative path. |
| `get_sharepoint_drive_item` | Reads metadata for a single file, folder, package, or unknown drive item. |
| `search_sharepoint_drive_items` | Searches files and folders inside a document-library drive. |
| `ingest_sharepoint_drive_item` | Streams a file into the GCS Landing Zone and returns `gcs_uri`, `mime_type`, and `inject_file_data=true`. |

## Landing Zone Ingestion

`ingest_sharepoint_drive_item` never returns raw file bytes to the agent. It validates access by downloading the file using the delegated Microsoft token, then streams the file to:

```text
gs://{LANDING_ZONE_BUCKET}/{app_name}/{user_id}/{session_id}/sharepoint-{UTC_TIMESTAMP}-{original_filename}
```

The original SharePoint filename is preserved exactly as returned by Microsoft Graph. After upload, the MCP server grants the signed-in user `roles/storage.objectAdmin` only for their `{app_name}/{user_id}/` namespace using the `uploader-folder-access` IAM condition.

## Local Development

```bash
uv run --group mcp_sharepoint python -m mcp_servers.sharepoint.app.main --host localhost --port 8086
```

Run tests:

```bash
uv run --group mcp_sharepoint pytest mcp_servers/sharepoint/tests/
```
