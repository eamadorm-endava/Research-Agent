# Core ADK Agent

This folder contains the ADK agent that is deployed to Vertex AI Agent Engine and surfaced through Gemini Enterprise.

## Current integration pattern

- **BigQuery** is consumed through a remote MCP server.
- **Google Drive** is consumed through a remote MCP server via `McpToolset`, matching the same `mcp_servers/<service>/app/...` layout as BigQuery.
- The Drive MCP integration now supports two authentication layers:
  - **MCP-service authentication** through `McpToolset(auth_scheme=..., auth_credential=...)` when the Drive MCP endpoint itself sits behind an API gateway or OAuth2-protected ingress.
  - **Delegated user Drive authentication** through `header_provider`, which forwards the Gemini Enterprise user token to the MCP server on each request.
- The legacy in-process Drive tools are still present as a fallback, but the preferred runtime path is the Drive MCP server.

## Folder structure

```text
agent/core_agent/
├── __init__.py
├── agent.py
├── config.py
├── model_armor.py
├── .env.example
└── utils/
    └── security.py
```

## Required `.env` placement

Place the `.env` file directly inside `agent/core_agent/`.

At minimum, configure:

```env
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=mock-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
PROJECT_ID=${GOOGLE_CLOUD_PROJECT}
REGION=${GOOGLE_CLOUD_LOCATION}
MODEL_ARMOR_TEMPLATE_ID=mock-model-armor-template-id

# Gemini Enterprise delegated Drive OAuth
GEMINI_ENTERPRISE_AUTH_ID=drive-oauth

# Google Drive MCP server
DRIVE_URL=http://localhost:8081
DRIVE_ENDPOINT=/mcp
DRIVE_DELEGATED_TOKEN_HEADER=x-drive-access-token
DRIVE_DISABLE_ID_TOKEN_AUTH=true

# Optional authentication for the MCP service itself
DRIVE_MCP_AUTH_MODE=none
DRIVE_MCP_AUTH_HEADER_NAME=Authorization
DRIVE_MCP_AUTH_TOKEN=
DRIVE_MCP_OAUTH_CLIENT_ID=
DRIVE_MCP_OAUTH_CLIENT_SECRET=
DRIVE_MCP_OAUTH_TOKEN_URL=
DRIVE_MCP_OAUTH_AUTH_URL=
DRIVE_MCP_OAUTH_SCOPES=
```

## Local testing flow

1. Start the Drive MCP server:

```bash
make run-drive-mcp-locally
```

2. Start the ADK web UI:

```bash
make run-ui-agent
```

3. Ask the agent to search Drive, fetch file text, or create a doc.

For local Drive auth, enable one of the following in the Drive MCP server environment:

- `DRIVE_ALLOW_LOCAL_OAUTH=true`
- `DRIVE_USE_ADC=true`

## Deployment pattern

In production, the agent can call the Drive MCP server using up to two layers of auth:

- **MCP service auth** for reaching the Drive MCP endpoint itself:
  - a **Cloud Run ID token** in `Authorization` when the service is protected by Cloud Run IAM, or
  - an ADK-managed `auth_scheme` / `auth_credential` pair when the MCP endpoint is protected by an OAuth2-capable gateway or another token-based auth layer.
- **Delegated user Drive auth** in `x-drive-access-token` (or your configured header name) so the MCP server can call Google Drive on the user's behalf.

That delegated token originates from Gemini Enterprise authorization attached to the agent registration. The code intentionally keeps delegated Drive access in `header_provider` so the token can vary per user/session while still allowing optional static MCP-service auth through `McpToolset`.
