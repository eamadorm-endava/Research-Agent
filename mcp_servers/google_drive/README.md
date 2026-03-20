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

This service relies on native MCP authentication middleware. The agent handles the OAuth process, and this server validates the provided token.

- **Token Validation**: The server uses a `TokenVerifier` to validate the access token against Google's `tokeninfo` endpoint.
- **Token Usage**: Each tool retrieves the access token from the MCP context and uses it to call the Google Drive API.

### Downstream Drive Credentials
This server uses a **delegated user access token header** (recommended for Gemini Enterprise).
- Header name defaults to `Authorization: Bearer <token>`.
- The MCP middleware automatically extracts and validates this token.

## Local run

```bash
uv run --group mcp_drive python -m mcp_servers.google_drive.app.main --host localhost --port 8081
```

## Cloud Run / Gemini Enterprise

In production, the agent calls this server with:
- `Authorization: Bearer <delegated-user-oauth-access-token>` (or another token handled by the MCP auth layer).

The delegated access token comes from Gemini Enterprise authorization configured on the agent registration. The ADK framework handles the token propagation.
