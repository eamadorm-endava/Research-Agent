# BigQuery MCP Server

This connector is built using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) and the [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk). It provides a secure, modular server that exposes Google Cloud BigQuery operations as asynchronous tools for AI Agents.

This MCP Server was created because the official MCP server for BigQuery only allows very basic, read-only queries, which acts as a limitation when trying to leverage the full capabilities of AI Agents.

## Available Tools

This MCP server provides the following advanced BigQuery tools (write/read) to the Agent:
- `create_dataset`: Create new BigQuery datasets with specific locations.
- `list_dataset`: List all datasets available in a project.
- `create_table`: Create new tables with specified schemas using `SCHEMA_DEFINITION`.
- `get_table_schema`: Retrieve the field schema of a specific table for introspection.
- `list_tables`: List all tables in a given dataset for agent discovery.
- `add_rows`: Efficiently insert multiple records into an existing table using `ROWS`.
- `execute_query`: Run read-only standard SQL queries. Enforces safety by blocking destructive commands (`DROP`, `DELETE`, `TRUNCATE`).

## Tool Enhancements
Compared to previous iterations, the following major improvements were made to the BigQuery Tools:

-   **Asynchronous Execution**: All tools are implemented using `async def`. Heavy I/O operations with the BigQuery SDK are wrapped in `asyncio.to_thread` to ensure the MCP server remains responsive under load.
-   **Strict Validation**: Powered by Pydantic.
    -   **Project IDs**: Validated against an allowed list via `AvailableProject(StrEnum)`.
    -   **Resource IDs**: Dataset and Table IDs are strictly validated via regex (`^[\w-]+$`) and length constraints.
    -   **Unified Types**: Uses `SCHEMA_DEFINITION` for structures and `ROWS` for data blocks to ensure semantic consistency.
-   **Error Handling via `execution_status` and `execution_message`**: Tools now include these keys in their responses. This allows wrapping any error during tool execution in `try/except` blocks, preventing the connection with the agent from breaking and allowing the agent to retry proactively if necessary.
-   **Structured I/O with Pydantic Models**: Tool inputs and outputs are now strictly specified through Pydantic models (based on the `BaseModel` class). This enables deep data validation, significantly reducing the odds of the agent sending poorly formatted parameters.
-   **Support for Complex/Nested BigQuery Columns**: Agents usually struggle to write complex JSON bodies due to a lack of specificity. By implementing Pydantic models, we clearly define specifics such as non-null strings, regex-validated parameters, and nested JSON arrays. This makes the agentic system much more robust and capable of handling higher dataset complexities when creating tables.
-   **Malicious Keyword Validation**: Previously, the agent could be tricked into executing malicious queries via back-and-forth prompt injection. Through Pydantic's data validation and a helper function that checks for dangerous keywords (`DROP`, `DELETE`, `TRUNCATE`) inside the `execute_query` tool, this vulnerability is fundamentally patched. *(Note: Model Armor does not actively search for this specific type of malicious SQL prompt).*

## 🚀 Architecture & Performance Improvements

-   **Migrated Transport to `StreamableHTTP`**: The MCP server (and the connecting agent) were updated to use the `streamable-http` transport instead of standard SSE. StreamableHTTP establishes a more efficient, bidirectional, chunked connection over a single `/mcp` endpoint. This improves performance by eliminating the need to manage separate event streams and POST request endpoints, drastically reducing network overhead and latency for tool execution.
-   **Docker Runtime Execution via `uv`**: The Dockerfile `CMD` was updated to execute the ASGI app directly using `uv run`. This ensures the container strictly runs using the exact locked dependencies from `uv.lock` within the specific `mcp_bq` group. It improves deployment reliability by creating a deterministic environment and avoiding complex virtual environment management in production.
-   **Dynamic Port Binding**: The application entrypoint (`main.py`) was refactored to accept `--host` and `--port` arguments, and the Dockerfile now injects Cloud Run's native `$PORT` environment variable. This guarantees seamless deployments across different environments without hardcoding ports.
-   **Secured Authentication**: The Terraform infrastructure (`main.tf`) was hardened by removing the `allUsers` IAM binding. The service now aggressively rejects unauthenticated HTTP requests. This heavily improves security by forcing the ADK Agent (or any client) to authenticate using valid Google Cloud credentials via `mcp_headers`, protecting the BigQuery data from public access.

## Connection Guide for Agents

Your MCP-compatible agent will automatically discover the tools and their parameters.

1.  **Transport Protocol**: StreamableHTTP over HTTP.
2.  **Endpoint URL**:
    *   **Local Testing**: `http://localhost:8080/mcp`
    *   **Production**: `https://[CLOUD_RUN_SERVICE_URL]/mcp`
3.  **Authentication**:
    *   **MCP OAuth**: The server expects `Authorization: Bearer <delegated-user-oauth-access-token>` and validates it through MCP auth middleware.
    *   **Cloud Run IAM**: If service ingress is protected, the caller also needs `X-Serverless-Authorization: Bearer <google-id-token>` for Cloud Run invocation.

## Security & Authentication (Delegated User Access)

This server relies on a **delegated end-user OAuth access token** propagated by ADK/Gemini Enterprise through the MCP `Authorization` header. No JSON key files are required.

### Key Benefits
- **Least-Privilege Data Access**: Queries run with the requesting user's BigQuery permissions, not a broad backend identity.
- **Safer Failure Mode**: Unauthorized attempts return `execution_status="error"` with a `Permission Denied` message instead of data.
- **Reduced Credential Exposure Risk**: Tokens are handled through MCP auth context and are not logged by the tool handlers.

### 1. In Production (Cloud Run)
-   Create a Service Account with restricted BigQuery roles (e.g., `roles/bigquery.dataEditor`, `roles/bigquery.jobUser`).
-   Deploy Cloud Run specifying this service account:
    ```bash
    gcloud run deploy bigquery-mcp-server --image IMAGE_URL --service-account="[SA_EMAIL]"
    ```

### 2. Local Development
For end-to-end auth parity with Gemini Enterprise, send a valid user OAuth access token as `Authorization: Bearer <token>` when invoking `/mcp`.

If you are only validating Cloud Run ingress, also include an ID token in `X-Serverless-Authorization`.

---

## Local Development

This project uses `uv` for dependency management with a unified `pyproject.toml` in the repository root.

1.  **Dependencies**: Sync the BigQuery specific group:
    ```bash
    uv sync --group mcp_bq
    ```
2.  **Environment**: Run `make gcloud-auth` to configure your project and credentials.
3.  **Run Server**: Start the server using the provided Makefile:
    ```bash
    make run-bq-mcp-locally
    ```
4.  **Testing**: Run the modernized async test suite:
    ```bash
    make run-bq-tests
    ```