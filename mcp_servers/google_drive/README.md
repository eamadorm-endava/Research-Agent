# Google Drive MCP Server

This MCP server exposes Google Drive read, write, and workspace-organization operations through a remote Streamable HTTP MCP endpoint.
It mirrors the structure of the existing `mcp_servers/big_query` service, but it supports delegated user access to Google Drive.

## Exposed tools

- `list_files`
- `get_file_text`
- `create_google_doc`
- `upload_pdf`
- `create_file`
- `create_folder`
- `move_file`
- `rename_file`

## Metadata returned by list/search operations

List and search results now return enriched metadata, including:

- `size`
- `parents`
- `owners`
- `version`
- `createdTime`
- synthetic `path`

The synthetic `path` is resolved by traversing the Drive parent chain and is intended to give the agent clearer spatial context, for example `/Documents/Project/notes.txt`.

## Authentication model

This service relies on native MCP authentication middleware. The agent handles the OAuth process, and this server validates the provided token.

- **Token Validation**: The server uses a `TokenVerifier` to validate the access token against Google's `tokeninfo` endpoint.
- **Token Usage**: Each tool retrieves the access token from the MCP context and uses it to call the Google Drive API.

### Downstream Drive Credentials
This server uses the delegated user access token provided by the MCP auth layer.

- Default scope requirement is `https://www.googleapis.com/auth/drive`.
- This allows the server to manage files and folders beyond those created by the MCP application itself.

## Local run

```bash
uv run --group mcp_drive python -m mcp_servers.google_drive.app.main --host localhost --port 8081
```

## Cloud Run / Gemini Enterprise

In production, the agent calls this server with a delegated user access token obtained through Gemini Enterprise authorization.
The MCP middleware validates the token and exposes it to tools through the request context.
