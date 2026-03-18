# Basic LLM Agent Type Creation

The main idea of this folder is to develop a basic agent that can be deployed in [Vertex AI Agent Engine](https://docs.cloud.google.com/agent-builder/agent-engine/overview) and connected to [Gemini Enterprise](https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise).

The agent to be developed is an [**LLM Agent**](../../docs/ADK/ADK-01-Intro.md#llm-agents-llmagent-agent) type.

## Folder Structure

The `core_agent/` folder follows the [ADK project structure](https://google.github.io/adk-docs/get-started/quickstart/#project-structure) and contains the following files:

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
    DRIVE_OAUTH_CLIENT_ID=your-oauth-client-id.apps.googleusercontent.com
    DRIVE_OAUTH_CLIENT_SECRET=your-oauth-client-secret
    DRIVE_OAUTH_REDIRECT_URI=http://localhost:8000/oauth2callback

Notes:
- Set `BIGQUERY_URL` and `DRIVE_URL` to your deployed Cloud Run **base URL** (without `/mcp`).
- If you leave any URL empty, the corresponding MCP integration will be disabled automatically.
- The `DRIVE_OAUTH_` variables are required for the agent to authenticate users via the interactive Per-User OAuth 2.0 flow.

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

> **Authentication Status**: Currently, each MCP Server operates using its own dedicated Google Cloud Service Account, which holds the necessary backend permissions to access the resources (BigQuery datasets and Drive files). In the near future, this architecture will be upgraded to use **Per-User OAuth 2.0**, allowing the MCP servers to act on behalf of the specific end-user interacting with the agent.

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

**Why Choosing ModelArmorConfig**:
- **Lower Latency**: Google Cloud handles validation internally on their servers at high speed, eliminating multiple network round-trips
- **Simpler Integration**: No custom code needed - just configure template names
- **Better Performance**: Single validation within Vertex AI's infrastructure instead of callback-based validation

**How It Works**: 
- Your script sends the configuration to Vertex AI
- Vertex AI's internal Service Agent contacts Model Armor on your behalf for prompt/response sanitization
- Results are processed before and after generation

**Setup Requirement**: 
Grant the **Model Armor User** role (`roles/modelarmor.user`) to Vertex AI's internal Service Agent account:

- service-[gcp-project-number]@gcp-sa-aiplatform.iam.gserviceaccount.com 

This allows Vertex AI's backend to access and use your Model Armor templates on your behalf.
