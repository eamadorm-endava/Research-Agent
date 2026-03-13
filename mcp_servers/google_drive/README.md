# Google Drive MCP Server

This MCP server exposes Google Drive read and write operations through a remote Streamable HTTP MCP endpoint.
It mirrors the structure of the existing `mcp_servers/big_query` service, but it supports delegated user access to Google Drive.

## Exposed tools

- `list_files`
- `search_files`
- `get_file_text`
- `create_google_doc`
- `upload_pdf`

## Authentication model

This service supports two distinct auth concerns:

### 1) How the agent reaches the Drive MCP server
The agent connects with `McpToolset`, the same pattern used for BigQuery. The code supports:

- **Cloud Run ID token** via the ADK `header_provider` helper.
- Optional ADK-managed **`auth_scheme` / `auth_credential`** on `McpToolset` when the Drive MCP endpoint itself is protected by an OAuth2-capable gateway or another token-based auth layer.

### 2) How the Drive MCP server reaches Google Drive on behalf of the user
This server resolves downstream Drive credentials in the following order:

1. **Delegated user access token header** (recommended for Gemini Enterprise)
   - Header name defaults to `x-drive-access-token`.
   - Override with `DRIVE_DELEGATED_TOKEN_HEADER`.
2. **Application Default Credentials (ADC)** for service-account or local user testing.
   - Enable with `DRIVE_USE_ADC=true` or `USE_ADC_FOR_DRIVE=true`.
3. **Local OAuth** for development.
   - Enable with `DRIVE_ALLOW_LOCAL_OAUTH=true` or `ALLOW_LOCAL_OAUTH=true`.

## Local run

```bash
uv run --group mcp_drive python -m mcp_servers.google_drive.app.main --host localhost --port 8081
```

## Local end-to-end with the agent

1. Start this server locally.
2. Point the agent to `DRIVE_URL=http://localhost:8081` and `DRIVE_ENDPOINT=/mcp`.
3. For local auth, enable one of:
   - `DRIVE_ALLOW_LOCAL_OAUTH=true`
   - `DRIVE_USE_ADC=true`

## Cloud Run / Gemini Enterprise

In production, the agent can call this server with two layers of auth:

- `Authorization: Bearer <cloud-run-id-token>` so Cloud Run accepts the request, **or** an ADK-managed `auth_scheme` / `auth_credential` pair if the MCP endpoint is protected by another OAuth2-capable gateway.
- `x-drive-access-token: <delegated-user-oauth-access-token>` so the server can call the Drive API on the user's behalf.

The delegated access token comes from Gemini Enterprise authorization configured on the agent registration. The agent code keeps this delegated token in `header_provider` so it remains per-user and per-session.
