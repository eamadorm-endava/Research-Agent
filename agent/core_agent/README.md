# Core ADK Agent

This folder contains the ADK agent that is deployed to Vertex AI Agent Engine and surfaced through Gemini Enterprise.

## Current integration pattern

- **BigQuery** is consumed through a remote MCP server.
- **Google Drive** is now also consumed through a remote MCP server, matching the same `mcp_servers/<service>/app/...` layout.
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

In production, the agent calls the Drive MCP server using:

- a **Cloud Run ID token** in `Authorization` so Cloud Run accepts the request
- a **delegated user OAuth access token** in `x-drive-access-token` (or your configured header name) so the MCP server can call Google Drive on the user's behalf

That delegated token originates from Gemini Enterprise authorization attached to the agent registration.
