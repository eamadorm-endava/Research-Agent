---
trigger: always_on
description: "Guidelines and best practices for developing and structuring custom MCP Servers."
---

# mcp-server-guide.md

All MCP development must strictly adhere to these standards:
- **Enforces**: `@.agents/rules/coding-guide.md` for universal engineering principles.
- **Applies**: `@.agents/rules/backend-guide.md` for Python-specific patterns.

Follow these standards and architectural patterns when creating or modifying custom Model Context Protocol (MCP) servers within the `mcp_servers/` directory. These guidelines are based on the implementation standards found in the BigQuery and Calendar MCP servers.

### 1. Technology Stack
- **MCP Framework**: Use the **MCP Python SDK** (`mcp` package). Specifically, use `FastMCP` from `mcp.server.fastmcp` to expose tools.
- **Data Validation & Modeling**: Use **Pydantic** (`BaseModel`) for defining explicit `Request` and `Response` schemas for every tool.
- **Configuration**: Use **Pydantic Settings** (`BaseSettings`) for reading, validating, and grouping environment variables.

### 2. Standard Folder Structure
Each MCP server must follow this internal structure inside `mcp_servers/<server_name>/`:
```text
mcp_servers/<server_name>/
├── app/
│   ├── __init__.py
│   ├── config.py           # BaseSettings for environment variables
│   ├── main.py             # Entry point (runs the FastMCP server)
│   ├── mcp_server.py       # FastMCP instantiation, tool definitions, and token verification
│   ├── schemas.py          # Request and Response Pydantic models
│   ├── security.py         # (Optional) Token verifier implementations
│   └── <domain>/           # (Optional) Sub-packages for complex clients (e.g., calendar/, meet/)
│       ├── __init__.py
│       ├── client.py       # Domain-specific API wrapper
│       └── schemas.py      # Internal data structures returned by the client
├── tests/                  # Pytest unit and integration tests
├── Dockerfile              # Containerization for the MCP server
└── README.md               # Documentation and setup instructions
```

### 3. Implementation Best Practices

#### Configuration (`config.py`)
- Group configurations logically (e.g., `ServerConfig`, `APIConfig`).
- Never hardcode values. Define defaults if appropriate, but allow overrides via environment variables.

#### Schemas (`schemas.py`)
- **Mandatory Pattern**: Every `@mcp.tool()` must have a dedicated `<Action>Request` and `<Action>Response` model.
- Example: `ListCalendarEventsRequest` and `ListCalendarEventsResponse`.
- Ensure all fields include clear `description` metadata (using `Annotated` and `Field`).

#### Server Definition (`mcp_server.py`)
- Instantiate `FastMCP` globally within the file.
- **Authentication**: Custom MCP servers must implement the `token_verifier` pattern (e.g., `GoogleCalendarTokenVerifier`) and pass it to `FastMCP` via the `auth=AuthSettings(...)` parameter to validate incoming Gemini/OAuth tokens.
- **Validation & Thin Tools**: **MANDATORY**: All input parameter validation, complex regex parsing, and path construction MUST be handled within the Pydantic `Request` models (e.g., using `Field(pattern=...)`, `@property`, or `@model_validator`).
    - `@mcp.tool()` wrappers should only handle unpacking the request, calling the underlying client (via `asyncio.to_thread`), and packing the response.
    - Never include logic like `if not match: raise ValueError` inside the tool body; move it to the schema.
- **Tool Wrappers**: Catch exceptions and return them gracefully within the `Response` model (e.g., via an `execution_status` field).

#### Unified Clients (`app/<domain>/` or `app/client.py`)
- Do not put complex API logic directly inside the tool functions in `mcp_server.py`.
- Encapsulate external API calls within dedicated client classes (e.g., `EventsClient`, `GCSClient`).
- If an MCP server connects to multiple distinct sub-APIs (like Calendar and Meet), use a **Unified Wrapper** pattern (e.g., `connector.py` acting as an orchestrator) that delegates to specialized sub-clients.

### 4. External Data Ingestion (Landing Zone)
- Whenever an MCP Server needs to read or process files from external data sources (e.g., Google Drive, Confluence), it **MUST NOT** return the raw file content directly to the agent.
- Instead, the server must first upload/move the file into the central GCS Landing Zone bucket (`LANDING_ZONE_BUCKET`).
- The file must be stored using the exact folder naming convention required by the ADK Artifact system:
  `gs://{LANDING_ZONE_BUCKET}/<app_name>/<user_id>/<session_id>/<data_source>-<ingestion-timestamp-in-UTC>-<filename>.<extension>`
  *(Example: `gs://my-bucket/core_agent/user-email@domain.com/123434/google-drive-20231025T103000Z-session-recording.pdf`)*
- **Dependency Injection**: The `app_name`, `user_id` and `session_id` must be provided to the tool via Dependency Injection (e.g. from an agent wrapper). Do **NOT** expect the LLM to provide them. This injection must be explicitly defined in the tool's `Request` schema using a strongly-typed Pydantic model (e.g., `dependencies: Optional[AgentDependencies]`) and hidden from the LLM using an explicit description (e.g., `description="SYSTEM FIELD: Do NOT provide this parameter. It is automatically injected."`). Do NOT use `Field(exclude=True)` as it will cause the MCP Client to drop the parameter.
- **Lifecycle Management**: The files ingested into the Landing Zone must have a lifecycle parameter or be placed in a bucket with Object Lifecycle Management (OLM) rules applied. By default, these ephemeral files must exist in the bucket for **only 7 days**, after which they must be automatically deleted to prevent storage bloat.
- After uploading the file, the tool must return the GCS URI (`gcs_uri`), the MIME type (`mime_type`), and the flag `inject_file_data: True` as top-level attributes in its public `Response` schema so the `FileIngestionToolWrapper` can intercept it and load the file natively into the agent's context.