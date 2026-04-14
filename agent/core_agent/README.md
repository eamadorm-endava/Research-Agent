# Core ADK Agent

This package contains the ADK agent that is deployed to Vertex AI Agent Engine and surfaced through Gemini Enterprise.

The agent is an [**LLM Agent**](../../docs/ADK/ADK-01-Intro.md#llm-agents-llmagent-agent) type that integrates multiple Google data sources using **Model Context Protocol (MCP)** servers.

## Package Architecture

```
core_agent/
├── __init__.py          # Package entry point, exports the agent module
├── agent.py             # Application entry point, wires config → builder → agent
├── .env                 # Environment variables (Vertex AI, MCP URLs, OAuth)
│
├── config/              # Centralized Pydantic Settings (classes + singletons)
│   ├── __init__.py      # Re-exports classes and UPPER_CASE singleton instances
│   ├── agent_settings.py    # GCPConfig, AgentConfig, GoogleAuthConfig
│   └── mcp_settings.py     # BaseMCPConfig + per-service subclasses
│
├── builder/             # Builder pattern for agent construction
│   ├── __init__.py      # Re-exports AgentBuilder, MCPToolsetBuilder, get_skill_toolset
│   ├── agent_builder.py     # Fluent AgentBuilder orchestrator
│   ├── mcp_factory.py       # MCPToolsetBuilder (auth + connection setup)
│   └── skills_factory.py    # get_skill_toolset (ADK Skill loader)
│
└── security/            # Authentication utilities
    ├── __init__.py      # Re-exports get_id_token, get_ge_oauth_token
    └── auth.py          # GCP ID tokens + Gemini Enterprise OAuth delegation
```

## Module Overview

The package is organized into three internal modules, each with a single responsibility:

- **`config/`** — Centralized configuration management. Contains Pydantic `BaseSettings` classes that validate environment variables at import time. Exposes both the **classes** (for type hints and testing) and **singleton instances** (for runtime usage), so consumers never need to call `os.getenv()` directly.

- **`builder/`** — Agent construction logic. Separates the _what to build_ from the _how to build it_ using the Builder pattern. The `AgentBuilder` orchestrates the full agent assembly, while `MCPToolsetBuilder` and `get_skill_toolset` handle the specific construction of MCP connections and ADK skills respectively.

- **`security/`** — Token generation utilities. Provides functions to obtain GCP identity tokens (for Cloud Run service authentication) and Gemini Enterprise OAuth tokens (for delegated user data access). These are consumed by the builder at runtime, not at construction time.

The entry point `agent.py` wires everything together: it imports singletons from `config/`, passes them into `AgentBuilder`, and wraps the result in an `AdkApp` for deployment.

## How the Components Interact

The following sequence diagram shows the data flow between components during agent construction. **Solid arrows** (`→`) represent inputs passed to a component, and **dashed arrows** (`⇢`) represent the values returned back.

```mermaid
sequenceDiagram
    agent.py->>AgentBuilder: AgentConfig, GCPConfig, GoogleAuthConfig
    AgentBuilder->>MCPToolsetBuilder: GoogleAuthConfig
    agent.py->>AgentBuilder: skill names list
    AgentBuilder->>get_skill_toolset: skill name
    get_skill_toolset-->>AgentBuilder: SkillToolset
    agent.py->>AgentBuilder: MCP configs list
    AgentBuilder->>MCPToolsetBuilder: BaseMCPConfig, prod_execution
    MCPToolsetBuilder->>security: audience URL
    security-->>MCPToolsetBuilder: ID token
    MCPToolsetBuilder->>security: ReadonlyContext, auth_id
    security-->>MCPToolsetBuilder: OAuth token
    MCPToolsetBuilder-->>AgentBuilder: McpToolset
    agent.py->>AgentBuilder: .build()
    AgentBuilder-->>agent.py: Agent
```

### Reading the Diagram

1. **Initialization** — `agent.py` creates an `AgentBuilder` by passing the three configuration singletons. The builder internally instantiates an `MCPToolsetBuilder` with the auth config it needs.

2. **Skill registration** — When `agent.py` calls `.with_skills(...)`, the builder delegates each skill name to `get_skill_toolset`, which loads the skill from disk and returns a `SkillToolset`.

3. **MCP registration** — When `agent.py` calls `.with_mcp_servers(...)`, the builder passes each MCP config to `MCPToolsetBuilder.build()`. The MCP builder uses the `security` module to obtain an ID token (for Cloud Run access) and an OAuth token (for delegated user data), then returns a fully configured `McpToolset`.

4. **Final assembly** — `agent.py` calls `.build()`, which assembles the `Agent` with the accumulated tools, model settings, and planner. The returned `Agent` is then wrapped in `AdkApp` for deployment.

## Benefits of This Architecture

| Benefit | Description |
|---|---|
| **Separation of Concerns** | Configuration, building, security, and orchestration live in dedicated modules with clear single responsibilities |
| **Fluent API** | The builder pattern (`with_skills().with_mcp_servers().build()`) makes the construction flow readable and self-documenting |
| **Centralized Configuration** | All env vars are validated once through Pydantic, eliminating scattered `os.getenv()` calls and catching misconfigurations early |
| **Dual-Export Pattern** | The `config/` module exposes both **classes** (for type hints and testing) and **singletons** (for runtime), reducing boilerplate |
| **Environment Agnostic** | The `MCPToolsetBuilder` transparently handles local OAuth (ADK-managed) vs. production OAuth (Gemini Enterprise-managed) without leaking environment logic into the agent |
| **Testability** | Each builder can be unit-tested in isolation by injecting mock configs. The clear interfaces make mocking straightforward |
| **Extensibility** | Adding a new MCP server or skill requires only a new config class + adding it to the mount list in `agent.py` |

## Drawbacks and Trade-offs

| Drawback | Description |
|---|---|
| **Indirection** | The layered architecture (config → builder → factory → agent) adds navigation overhead when debugging end-to-end flows |
| **Singleton Coupling** | Module-level singletons (`GCP_CONFIG`, etc.) are instantiated at import time, which can conflict with test fixtures that need isolated environments |
| **Builder Complexity** | For a single-agent system, the full builder + factory pattern may feel over-engineered compared to a flat script. The value scales with the number of tools/configs |
| **Private API Dependency** | Some tests rely on internal attributes of ADK classes (e.g., `_skills`, `_connection_params`), which may break on library upgrades |

## Integrated Tools

The agent connects to backend services via **MCP servers** and exposes **ADK Skills**:

### MCP Servers
- **BigQuery**: Analytical queries against structured tables
- **Google Drive**: Read, list, and upload files
- **Google Calendar**: Upcoming events, schedule data, and Meet links
- **Google Cloud Storage (GCS)**: Search and read unstructured files from buckets

### ADK Skills
- **meeting-summary**: Summarizes meeting notes and action items

> **Authentication Model**: Drive, BigQuery, and Calendar share a delegated Google OAuth token so MCP servers act on behalf of the end-user. A Cloud Run ID token (`X-Serverless-Authorization`) secures the MCP Cloud Run service itself.

## Environment Setup

### Required `.env` file

Place the `.env` file directly inside `agent/core_agent/`:

```env
# ─── Vertex AI ───
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
PROJECT_ID=${GOOGLE_CLOUD_PROJECT}
REGION=${GOOGLE_CLOUD_LOCATION}

# ─── Agent Config ───
MODEL_ARMOR_TEMPLATE_ID=your-model-armor-template-id

# ─── Gemini Enterprise Delegated OAuth ───
GEMINI_GOOGLE_AUTH_ID=shared-oauth-resource-id

# ─── MCP Servers (optional, defaults to localhost) ───
BIGQUERY_URL=https://bigquery-mcp-server-xxxxx-uc.a.run.app
DRIVE_URL=https://google-drive-mcp-server-xxxxx-uc.a.run.app
CALENDAR_URL=https://calendar-mcp-server-xxxxx-uc.a.run.app
GCS_URL=https://gcs-mcp-server-xxxxx-uc.a.run.app

# ─── Local OAuth (for development only) ───
GOOGLE_OAUTH_CLIENT_ID=your-oauth-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-oauth-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/dev-ui
```

## How to Test Locally

### 1. Authenticate with GCP

```bash
gcloud auth application-default login --project your-gcp-project-id
gcloud config set project your-gcp-project-id
```

Or use the Makefile shortcut:

```bash
make gcloud-auth
```

### 2. Start the Agent Dev UI

```bash
make run-ui-agent
```

This runs `uv run adk web --port 8000` inside the `agent/` directory.

### 3. Run Tests

```bash
make test-agent
```

## Deployment Pattern

In production, the agent calls backend MCP servers using up to two layers of auth:

- **MCP service auth**: A Cloud Run ID token in `X-Serverless-Authorization` to reach the protected Cloud Run endpoint.
- **Delegated user data auth**: An OAuth token in `Authorization` so the MCP server can call Google APIs on behalf of the end-user.

The delegated token originates from Gemini Enterprise authorization attached to the agent registration (`GEMINI_GOOGLE_AUTH_ID`). The code injects this per-request via `header_provider` so each call reflects the specific user session.

---

> **⚠️ ADK Naming Convention**: The ADK CLI (`adk web`) expects a specific directory and variable structure to discover and run the agent locally. The folder must be named `core_agent` (matching the package import path), and the `agent.py` file must expose a variable called `root_agent` (the `Agent` instance) and `app` (the `AdkApp` wrapper). If the directory is renamed or these variables are moved, the ADK local Dev UI (`adk web`) will fail to locate the agent.
