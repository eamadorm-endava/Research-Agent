# Core ADK Agent

This package contains the ADK agent that is deployed to Vertex AI Agent Engine and surfaced through Gemini Enterprise.

The agent is an [**LLM Agent**](../../docs/ADK/ADK-01-Intro.md#llm-agents-llmagent-agent) type that integrates multiple Google and Microsoft data sources using **Model Context Protocol (MCP)** servers.

## Package Architecture

```
core_agent/
├── __init__.py          # Package entry point, exports the agent module
├── agent.py             # Application entry point, wires config → builders → agents → app
├── .env                 # Environment variables (Vertex AI, MCP URLs, OAuth)
│
├── config/              # Centralized Pydantic Settings (classes + singletons)
│   ├── __init__.py      # Re-exports classes and UPPER_CASE singleton instances
│   ├── agent_settings.py    # GCPConfig, BaseAgentConfig, CoordinatorConfig,
│   │                        # ResearchAgentConfig, IngestionAgentConfig, GoogleAuthConfig
│   └── mcp_settings.py     # BaseMCPConfig + per-service subclasses
│
├── builder/             # Builder pattern for agent and app construction
│   ├── __init__.py      # Re-exports AgentBuilder, AppBuilder, MCPToolsetBuilder
│   ├── agent_builder.py     # Fluent AgentBuilder orchestrator
│   ├── app_builder.py       # Orchestrates AdkApp vs. standard App construction
│   ├── mcp_factory.py       # MCPToolsetBuilder (auth + connection setup)
│   └── skills_factory.py    # get_skill (ADK Skill loader)
│
├── artifact_service/ # Infrastructure: GCS persistence and IAM security
│   ├── __init__.py      
│   ├── schemas.py       # Shared Request/Response models and state keys
│   └── service.py       # StorageService (Reference-based GCS storage)
│
├── tools/               # Agent Capabilities: Standalone tool definitions
│   ├── __init__.py      
│   ├── artifact_tools.py    # GetArtifactURITool, ImportGcsToArtifactTool
│   ├── kb_schemas.py        # Pydantic schemas for EKB pipeline tools
│   ├── ekb_tools/tools.py          # TriggerEKBPipelineTool, CheckIngestionStatusTool
│   └── time_tools.py        # GetCurrentTimeTool (Central Time)
│
├── callbacks/           # Lifecycle Hooks: Post-turn renderers and interceptors
│   ├── __init__.py      
│   ├── before_agent_callbacks/                             # Logic that runs before the agent starts
│   └── plugins/multimodal_file_injection/                  # Intercepts MCP Server data and natively injects it into the LLM contextors
│
├── plugins/             # Integrated Behaviors: Message interceptors
│   ├── __init__.py      
│   └── gemini_enterprise_ingestion/       # Gemini Enterprise file ingestion orchestrator
│
└── security/            # Authentication utilities
    ├── __init__.py      # Re-exports get_id_token, get_ge_oauth_token
    └── auth.py          # GCP ID tokens + Gemini Enterprise OAuth delegation
```

## Module Overview

The package is organized into dedicated domains, each with a single responsibility:

- **`config/`** — Centralized configuration management. Contains Pydantic `BaseSettings` classes that validate environment variables at import time: `GCPConfig` (project/region/bucket), `BaseAgentConfig` (model, generation, retry settings), and three per-agent subclasses — `CoordinatorConfig`, `ResearchAgentConfig`, and `IngestionAgentConfig` — each carrying the agent's name, description, and system prompt. Exposes both the **classes** (for type hints and testing) and **singleton instances** (for runtime usage), so consumers never need to call `os.getenv()` directly.

- **`artifact_service/`** — The infrastructure layer. Contains the `StorageService`, which handles low-level GCS operations, MIME type resolution, and identity-aware IAM binding conditions. It is optimized for Gemini Enterprise by using `file_data` URI references instead of binary payloads.

- **`builder/`** — Construction logic. Separates the _what to build_ from the _how to build it_ using the Builder pattern. The `AgentBuilder` orchestrates the core agent assembly, while the `AppBuilder` handles the final application wrapper (`AdkApp` for production or `App` for local), ensuring consistent plugin and storage configuration.

- **`tools/`** — Standalone capabilities. Explicitly registered with the agent to provide specific functionality (e.g., GCS URI retrieval).

- **`callbacks/`** — Lifecycle hooks and interceptors. Contains tools and callbacks like `file_ingestion` to dynamically inject generated files into the session.

- **`plugins/`** — Integrated behaviors. Contains message interceptors like the `GeminiEnterpriseFileIngestionPlugin` that manage user-uploaded artifacts before the agent processes the message.

- **`security/`** — Token generation utilities. Provides functions to obtain GCP identity tokens (for Cloud Run service authentication) and Gemini Enterprise OAuth tokens (for delegated user data access). These are consumed by the builders at runtime, not at construction time.

The entry point `agent.py` wires everything together: it imports singletons from `config/`, assembles the agent via `AgentBuilder`, and passes it to `AppBuilder` to create the final `app` instance.

## How the Components Interact

The following sequence diagram shows the data flow between components during agent construction. **Solid arrows** (`→`) represent inputs passed to a component, and **dashed arrows** (`⇢`) represent the values returned back.

```mermaid
sequenceDiagram
    participant ap as agent.py
    participant rb as AgentBuilder (research)
    participant ib as AgentBuilder (ingestion)
    participant cb as AgentBuilder (coordinator)
    participant mcp as MCPToolsetBuilder
    participant sec as security
    participant sf as get_skill
    participant ab as AppBuilder

    Note over ap,ab: ── 1. Research Specialist ──
    ap->>rb: ResearchAgentConfig, GCPConfig, GoogleAuthConfig
    rb->>mcp: GoogleAuthConfig
    ap->>rb: .with_skills(["meeting-summary","knowledge-discovery"])
    rb->>sf: skill name ×2
    sf-->>rb: SkillToolset ×2
    ap->>rb: .with_mcp_servers([BQ, Drive, Calendar, GCS])
    rb->>mcp: BaseMCPConfig, prod_execution ×5
    mcp->>sec: audience URL / ReadonlyContext
    sec-->>mcp: ID token / OAuth token
    mcp-->>rb: McpToolset ×4
    ap->>rb: .with_native_tools([GetArtifactUri, ImportGcs, GetCurrentTime, load_artifacts])
    ap->>rb: .with_output_key("research_context")
    rb-->>ap: research_agent

    Note over ap,ab: ── 2. Ingestion Specialist ──
    ap->>ib: IngestionAgentConfig, GCPConfig, GoogleAuthConfig
    ap->>ib: .with_skills(["kb-file-ingestion"])
    ap->>ib: .with_mcp_servers([BQ, GCS])
    ap->>ib: .with_native_tools([GetArtifactUri, ImportGcs, TriggerEKB, CheckStatus, load_artifacts])
    ib-->>ap: ingestion_agent

    Note over ap,ab: ── 3. Coordinator (root_agent) ──
    ap->>cb: CoordinatorConfig, GCPConfig, GoogleAuthConfig
    ap->>cb: .with_subagents([research_agent, ingestion_agent])
    ap->>cb: .with_before_agent_callback(sync_ekb_job_status)
    ap->>cb: .with_native_tools([GetArtifactUri, load_artifacts])
    cb-->>ap: root_agent

    Note over ap,ab: ── 4. App wrapping ──
    ap->>ab: root_agent, CoordinatorConfig, GCPConfig
    ab-->>ap: AdkApp / App
```

### Reading the Diagram

1. **Research Specialist** — Built first. Receives `ResearchAgentConfig`, loads two skills (`meeting-summary`, `knowledge-discovery`), mounts five MCP servers (BigQuery, Drive, Calendar, GCS, SharePoint), and registers native tools including `GetCurrentTimeTool` for time-anchored calendar queries. Its final text response is persisted to session state under `"research_context"` via `output_key`.

2. **Ingestion Specialist** — Built second. Receives `IngestionAgentConfig`, loads the `kb-file-ingestion` skill, mounts BigQuery and GCS MCP servers, and registers the EKB pipeline tools (`TriggerEKBPipelineTool`, `CheckIngestionStatusTool`).

3. **Coordinator** — Built last from `CoordinatorConfig`. Receives the two already-constructed specialists as `sub_agents` for LLM-transfer delegation. The `sync_ekb_job_status` function is registered as a `before_agent_callback`, so it polls pending EKB jobs and injects status updates into session history before every turn.

4. **Application wrapping** — `AppBuilder.build()` wraps `root_agent` in an `AdkApp` (production) or `App` (local), pre-configured with the `GeminiEnterpriseFileIngestionPlugin` and `StorageService` artifact backend.

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

## Gemini Enterprise Artifact Lifecycle

As documented in the Architecture guides, Gemini Enterprise requires explicit manual handling for file ingestion to prevent out-of-memory errors. The system uses a strict MVC triad:

1. **The Database (`StorageService`)**: Handles all GCS interactions and identity-aware IAM.
2. **The User Hook (`GeminiEnterpriseFileIngestionPlugin`)**: Intercepts huge binary payloads sent from the UI, saves them to GCS via `StorageService`, and rewrites the payload into a lightweight `file_data` zero-copy URI.
3. **The Interceptor Hook (`MultimodalFileInjectionPlugin`)**: Dynamically catches backend MCP servers generating files mid-turn and injects the zero-copy URI directly into the LLM context.

## Integrated Tools

The agent connects to backend services via **MCP servers** and exposes **ADK Skills**:

### MCP Servers
- **BigQuery**: Analytical queries against structured tables
- **Google Drive**: Read, list, and upload files
- **Google Calendar**: Upcoming events, schedule data, and Meet links
- **Google Cloud Storage (GCS)**: Search and read unstructured files from buckets
- **Microsoft SharePoint**: Read-only site, document library, file metadata, and landing-zone file copy access

### ADK Skills
- **meeting-summary** (Research Specialist): Generates structured meeting summary documents from transcripts or notes and saves them to Drive.
- **knowledge-discovery** (Research Specialist): Expert protocol for high-fidelity retrieval across EKB, BigQuery, Drive, Calendar, and GCS using contextual anchoring and parallel discovery.
- **kb-file-ingestion** (Ingestion Specialist): Orchestrates the upload, classification, metadata tagging, and pipeline triggering for documents entering the Enterprise Knowledge Base.

> **Authentication Model**: Drive, BigQuery, Calendar, and GCS share a delegated Google OAuth token; Microsoft MCP servers use a delegated Microsoft Graph OAuth token so they can act on behalf of the end-user. A Cloud Run ID token (`X-Serverless-Authorization`) secures the MCP Cloud Run service itself.

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

# ─── Execution Mode ───
PROD_EXECUTION=False          # Set to True in production (enables GE-managed OAuth)
LANDING_ZONE_BUCKET=your-landing-zone-bucket-name

# ─── Agent Config ───
MODEL_ARMOR_TEMPLATE_ID=your-model-armor-template-id   # Omit to disable Model Armor

# ─── EKB Pipeline ───
EKB_PIPELINE_URL=https://ekb-pipeline-xxxxx-uc.a.run.app

# ─── Gemini Enterprise Delegated OAuth ───
GEMINI_GOOGLE_AUTH_ID=shared-oauth-resource-id

# ─── MCP Servers (optional, defaults to localhost) ───
BIGQUERY_URL=https://bigquery-mcp-server-xxxxx-uc.a.run.app
DRIVE_URL=https://google-drive-mcp-server-xxxxx-uc.a.run.app
CALENDAR_URL=https://calendar-mcp-server-xxxxx-uc.a.run.app
GCS_URL=https://gcs-mcp-server-xxxxx-uc.a.run.app
SHAREPOINT_URL=https://sharepoint-mcp-server-xxxxx-uc.a.run.app
GEMINI_MICROSOFT_AUTH_ID=microsoft-oauth-resource-id

# ─── Local OAuth (for development only) ───
GOOGLE_OAUTH_CLIENT_ID=your-oauth-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-oauth-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/dev-ui
MICROSOFT_OAUTH_CLIENT_ID=your-entra-application-client-id
MICROSOFT_OAUTH_CLIENT_SECRET=your-entra-client-secret
MICROSOFT_OAUTH_REDIRECT_URI=http://localhost:8000/dev-ui
MICROSOFT_GRAPH_OAUTH_SCOPES=["User.Read", "Files.Read.All", "Sites.Read.All", "offline_access"]
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
- **Delegated user data auth**: An OAuth token in `Authorization` so the MCP server can call Google or Microsoft Graph APIs on behalf of the end-user.

The delegated token originates from Gemini Enterprise authorization attached to the agent registration (`GEMINI_GOOGLE_AUTH_ID` for Google APIs and `GEMINI_MICROSOFT_AUTH_ID` for Microsoft Graph). The code injects this per-request via `header_provider` so each call reflects the specific user session.

---

> **⚠️ ADK Naming Convention**: The ADK CLI (`adk web`) expects a specific directory and variable structure to discover and run the agent locally. The folder must be named `core_agent` (matching the package import path), and the `agent.py` file must expose a variable called `root_agent` (the `Agent` instance) and `app` (the `AdkApp` wrapper). If the directory is renamed or these variables are moved, the ADK local Dev UI (`adk web`) will fail to locate the agent.
 