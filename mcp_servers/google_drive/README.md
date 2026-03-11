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

This service supports three credential sources, in order:

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

In production, the agent should call this server with two headers:

- `Authorization: Bearer <cloud-run-id-token>` so Cloud Run accepts the request.
- `x-drive-access-token: <delegated-user-oauth-access-token>` so the server can call the Drive API on the user's behalf.

The delegated access token comes from Gemini Enterprise authorization configured on the agent registration.
