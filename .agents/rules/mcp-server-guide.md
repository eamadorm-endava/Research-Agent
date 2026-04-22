---
trigger: always_on
glob: "**/mcp_servers/**/*"
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
- **Tool Wrappers**: Tools defined using `@mcp.tool()` should only handle request unpacking, calling the underlying client (often using `asyncio.to_thread` if the client is synchronous), and packing the response model. They should catch exceptions and return them gracefully within the `Response` model (e.g., via an `execution_status` field).

#### Unified Clients (`app/<domain>/` or `app/client.py`)
- Do not put complex API logic directly inside the tool functions in `mcp_server.py`.
- Encapsulate external API calls within dedicated client classes (e.g., `EventsClient`, `GCSClient`).
- If an MCP server connects to multiple distinct sub-APIs (like Calendar and Meet), use a **Unified Wrapper** pattern (e.g., `connector.py` acting as an orchestrator) that delegates to specialized sub-clients.
