# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Setup
```bash
uv sync --all-groups          # Install all dependency groups
make gcloud-auth              # Authenticate with GCP (ADC + project)
uvx pre-commit install        # Install git hooks
```

### Running the Agent
```bash
make run-ui-agent             # Start ADK Dev UI at http://localhost:8000
```

### Running Tests
```bash
make test-agent               # Agent unit tests
make run-bq-tests             # BigQuery MCP integration tests
make run-gcs-tests            # GCS MCP integration tests
make run-drive-tests          # Drive MCP integration tests
make run-calendar-tests       # Calendar MCP integration tests
make run-ekb-tests            # EKB pipeline tests

# Run a single test file
cd agent && uv run --group ai-agent --group dev pytest tests/test_builder.py -v
```

### Linting and Pre-commit
```bash
make run-precommit            # Run ruff linter + formatter + terraform fmt on all files
make run-agent-precommit      # Run only on agent files
make verify-all-ci            # Full CI check for all components
```

### Local MCP Servers
```bash
make run-bq-mcp-locally       # BigQuery MCP on port 8080
make run-drive-mcp-locally    # Drive MCP on port 8081
make run-gcs-mcp-locally      # GCS MCP on port 8082
make run-calendar-mcp-locally # Calendar MCP on port 8083
```

### Docker
```bash
make build-bq-mcp-image
make build-gcs-mcp-image
make build-drive-mcp-image
make build-calendar-mcp-image
```

### Agent Deployment
```bash
make deploy-agent             # Export requirements + deploy to Vertex AI Agent Engine
```

## Architecture

### Three-Layer System

**AI Agent** (`agent/core_agent/`) — An ADK `LLMAgent` deployed on Vertex AI Agent Engine and surfaced through Gemini Enterprise. It orchestrates tools from MCP servers, ADK skills, and internal tools.

**MCP Servers** (`mcp_servers/`) — Four independent FastMCP services (BigQuery, GCS, Google Drive, Google Calendar) deployed as Cloud Run services. Each exposes CRUD operations over Google APIs, does its own OAuth token verification, and builds Google API clients from the caller's delegated credentials.

**Data Pipelines** (`pipelines/enterprise_knowledge_base/`) — A FastAPI service that orchestrates document classification (DLP + Gemini) and RAG ingestion (chunk → embed → store in BigQuery) for an enterprise knowledge base. Deployed as a Cloud Run container.

### Agent Construction (Builder Pattern)

`agent.py` is the entry point. It assembles the agent via a fluent builder chain:

```python
root_agent = (
    AgentBuilder(agent_config, gcp_config, auth_config)
    .with_skills(["meeting-summary"])
    .with_mcp_servers([BQ_CONFIG, DRIVE_CONFIG, ...])
    .with_internal_tools([GetArtifactUriTool(), ImportGcsToArtifactTool(), load_artifacts])
    .build()
)
```

- `AgentBuilder` (`builder/agent_builder.py`) — Orchestrates the full assembly. Creates an `MCPToolsetBuilder` internally.
- `MCPToolsetBuilder` (`builder/mcp_factory.py`) — Builds each `McpToolset`. Injects auth headers via a runtime closure: an ID token in `X-Serverless-Authorization` (Cloud Run gateway) and, in production, an OAuth token in `Authorization` (Gemini Enterprise delegated user identity).
- `get_skill_toolset` (`builder/skills_factory.py`) — Loads ADK skills from `agent/skills/<name>/` by directory name.
- Internal tools (`internal_tools/artifact_tools.py`) — `GetArtifactUriTool` and `ImportGcsToArtifactTool` bridge ADK session artifacts and GCS URIs, enabling multimodal file analysis.

### Configuration (Pydantic Settings Singletons)

All env vars are validated at import time via `pydantic_settings.BaseSettings` classes in `agent/core_agent/config/`. The `config/__init__.py` exports both **classes** (for type hints and tests) and **module-level singleton instances** (for runtime use). Never call `os.getenv()` directly; always go through these singletons. Each MCP server has its own `BaseMCPConfig` subclass with per-service OAuth scopes and auth IDs.

Env files are loaded from `agent/core_agent/.env`. Key vars:
- `IS_DEPLOYED=false` → switches agent from `AdkApp` (Vertex AI) to plain `App` (local `adk web`)
- `BIGQUERY_URL`, `DRIVE_URL`, `GCS_URL`, `CALENDAR_URL` → MCP server endpoints (default to localhost)
- `GEMINI_GOOGLE_AUTH_ID` → Gemini Enterprise OAuth resource ID for delegated auth

### Local vs. Production Execution

The `GCP_CONFIG.PROD_EXECUTION` flag (aliased from `IS_DEPLOYED`) controls two behaviors:
1. **App type** (`agent.py`): `AdkApp` (production, Vertex AI) vs. `App` (local, `adk web`)
2. **MCP auth** (`mcp_factory.py`): In local mode, ADK manages the OAuth flow using `GOOGLE_OAUTH_*` credentials. In production, Gemini Enterprise injects the user token via `GEMINI_GOOGLE_AUTH_ID` and the agent retrieves it from `ReadonlyContext.state`.

### GCS MCP Authority Model

The GCS MCP server (`mcp_servers/gcs/app/mcp_server.py`) selects credentials per-call:
- **User credentials** (delegated OAuth token from the request) — used for user-bucket operations
- **Service Account (ADC)** — used when both source and destination are "internal pipeline buckets" (configured in `GCS_SERVER_CONFIG.internal_pipeline_buckets`)

This is how files flow from the agent's landing zone to a user's bucket without requiring user permissions on internal buckets.

### ADK Naming Constraints

The ADK CLI (`adk web`) discovers the agent by convention:
- The package directory must be named `core_agent`
- `agent.py` must expose `root_agent` (the `Agent` instance) and `app` (the `AdkApp` or `App` wrapper)
- Skills must live in `agent/skills/<skill-name>/` as directories

Renaming any of these breaks local `adk web` discovery.

### Dependency Groups

`pyproject.toml` uses `uv` dependency groups — not extras. Each component has its own group:
- `ai-agent` — Agent and ADK dependencies
- `mcp_bq`, `mcp_gcs`, `mcp_drive`, `mcp_calendar` — per-MCP-server deps
- `classification_pipeline`, `rag_pipeline`, `ekb-integration` — EKB pipeline deps
- `dev` — test/dev tooling shared across components

Always pass the correct `--group` flags when using `uv run` to avoid cross-component dependency pollution.

### Infrastructure

Terraform lives in `terraform/`. Apply order matters: `shared_resources/` → `ai_agent_resources/` → MCP service modules. CI/CD runs `terraform plan` on PR and `terraform apply` on merge to `main` via Cloud Build.
