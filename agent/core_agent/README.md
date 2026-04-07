# Core ADK Agent

This folder contains the ADK agent that is deployed to Vertex AI Agent Engine and surfaced through Gemini Enterprise.

The agent to be developed is an [**LLM Agent**](../../docs/ADK/ADK-01-Intro.md#llm-agents-llmagent-agent) type.

- **BigQuery** is consumed through a remote MCP server.
- **Google Drive** is consumed through a remote MCP server via `McpToolset`, matching the same `mcp_servers/<service>/app/...` layout as BigQuery.
- The Drive and BigQuery MCP integrations now share the same delegated Google OAuth token.
  - **MCP-service authentication** still happens through `X-Serverless-Authorization` so the agent can invoke the Cloud Run service.
  - **Delegated user data access** is forwarded through `Authorization`, so Drive and BigQuery calls run with the end-user's permissions.
- The legacy in-process Drive tools are still present as a fallback, but the preferred runtime path is the Drive MCP server.

## Folder structure

- `__init__.py` -> Package initialization file, imports the agent module
- `agent.py` -> Main agent definition with LLM Agent implementation
- `config.py` -> Configuration settings for the agent
- `model_armor.py` -> Custom Model Armor implementation class
- `utils/auxiliars.py` -> MCP helper utilities (builds `McpToolset` list from MCP config)
- `utils/security.py` -> Security utilities (handles generating Identity Tokens for GCP service authentication)
- `.env` -> Environment variables for model authentication (needed by the ADK CLI)

The .env file must be set directly inside `/core_agent` and must have the following variables:

    GOOGLE_GENAI_USE_VERTEXAI=TRUE
    GOOGLE_CLOUD_PROJECT=mock-gcp-project-id
    GOOGLE_CLOUD_LOCATION=mock-location
    PROJECT_ID=${GOOGLE_CLOUD_PROJECT}
    REGION=${GOOGLE_CLOUD_LOCATION}
    MODEL_ARMOR_TEMPLATE_ID=mock-model-armor-template-id

Optional MCP server variables:

    BIGQUERY_URL=https://bigquery-mcp-server-xxxxx-uc.a.run.app
    BIGQUERY_ENDPOINT=/mcp
    DRIVE_URL=https://google-drive-mcp-server-xxxxx-uc.a.run.app
    DRIVE_ENDPOINT=/mcp
    GOOGLE_OAUTH_CLIENT_ID=your-oauth-client-id.apps.googleusercontent.com
    GOOGLE_OAUTH_CLIENT_SECRET=your-oauth-client-secret
    GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/oauth2callback
    BIGQUERY_OAUTH_SCOPES=["https://www.googleapis.com/auth/bigquery"]

Notes:
- Set `BIGQUERY_URL` and `DRIVE_URL` to your deployed Cloud Run **base URL** (without `/mcp`).
- If you leave any URL empty, the corresponding MCP integration will be disabled automatically.
- The `GOOGLE_OAUTH_` variables identify the shared Google OAuth client used by the Drive and BigQuery MCP toolsets.
- `BIGQUERY_OAUTH_SCOPES` lets you extend the delegated token with BigQuery access for local testing.

MCP tool wiring is centralized in `get_mcp_servers_tools` inside `utils/auxiliars.py`, so `agent.py` stays focused on agent configuration and initialization.

## How to test the Agent Locally

There are [three ways](https://google.github.io/adk-docs/get-started/quickstart/#run-your-agent) to test the agent, here it is explained how to test it using the **Dev UI**

### 1. Authenticate in GCP 

As the project uses Vertex AI to connect with Gemini models, it is required to previously authenticate with Google Cloud using the gcloud CLI.

To do so, open the terminal and run:

    gcloud auth application default login --project mock-gcp-project-id
    gcloud config set project mock-gcp-project-id

Or you can run the make command (the terminal must be at the root of this repository):

    make gcloud-auth

### 2. Execute the ADK CLI comand

As ADK was installed using uv, it is needed to execute the command inside uv.

Open the terminal in the `agent/` folder, and run:

    uv run adk web --port 8000

Also, you can run the make command (make sure to be at the root of this repository):

    make run-ui-agent

## Agent Capabilities

This agent takes advantage of the [ADK tools and integrations](https://google.github.io/adk-docs/integrations/) to quickly implement required functionality. ADK provides pre-built tools for common use cases, and also supports creating custom [function-calling tools](https://google.github.io/adk-docs/tools-custom/function-tools/) for specific business needs.

### Implemented Tools

This agent connects to robust backend tools by consuming **Model Context Protocol (MCP)** servers dynamically:

- **BigQuery MCP Server**: Enables the agent to execute analytical queries against structural tables.
- **Google Drive MCP Server**: Connects the agent directly to Google Drive, allowing it to read, list, and upload files.

> **Authentication Status**: Drive and BigQuery now use a shared delegated Google OAuth token, so both MCP servers act on behalf of the specific end-user interacting with the agent. The Cloud Run identity token is kept only for invoking the protected MCP service itself.

### Security: Model Armor Implementation

**Model Armor** is a security guardrail mechanism integrated into Vertex AI that protects agents from malicious inputs and unsafe outputs. It validates prompts and responses for harmful content, prompt injections, and jailbreak attempts.

**Two Implementation Approaches**:

#### 1. Custom Callback Class (Requires Implementation)
Implement a custom safety evaluation class using ADK [Callbacks](https://google.github.io/adk-docs/callbacks/):
- **Before Agent Callback**: Intercepts and validates user inputs before the agent processes them
- **After Agent Callback**: Validates the agent's final output before returning it to the user

This approach provides full control and customization but requires:
- Writing custom Model Armor evaluation logic (currently, a version of this can be reviewed in [`model_armor.py`](/agent/core_agent/model_armor.py))
- Handling multiple network round-trips (Python → Model Armor API → Vertex AI → Model Armor)
- Increased latency due to sequential network calls
- Setting appropriate permissions for your service account

#### 2. Native ModelArmorConfig (**Current Implementation**)
Integrate Model Armor directly into `GenerateContentConfig` at the model level:

```python
ModelArmorConfig(
    prompt_template_name=model_armor_template_id,
    response_template_name=model_armor_template_id,
)
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
