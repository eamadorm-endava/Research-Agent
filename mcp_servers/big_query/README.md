# BigQuery Connector (MCP Server)

This connector is built using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) and Python's **FastMCP**. It provides a secure, modular server that exposes Google Cloud BigQuery operations as asynchronous tools for AI Agents.

## 🌟 Server Capabilities

The MCP Server wraps the `google-cloud-bigquery` client and exposes the following tools:

-   **`create_dataset`**: Create new BigQuery datasets with specific locations.
-   **`list_datasets`**: List all datasets available in a project.
-   **`create_table`**: Create new tables with specified schemas using `SCHEMA_DEFINITION`.
-   **`get_table_schema`**: Retrieve the field schema of a specific table for introspection.
-   **`list_tables`**: List all tables in a given dataset for agent discovery.
-   **`add_rows`**: Efficiently insert multiple records into an existing table using `ROWS`.
-   **`execute_query`**: Run read-only standard SQL queries. Enforces safety by blocking destructive commands (`DROP`, `DELETE`, `TRUNCATE`).

## 🛠️ Architecture

-   **Asynchronous Execution**: All tools are implemented using `async def`. Heavy I/O operations with the BigQuery SDK are wrapped in `asyncio.to_thread` to ensure the MCP server remains responsive under load.
-   **Strict Validation**: Powered by Pydantic.
    -   **Project IDs**: Validated against an allowed list via `AvailableProject(StrEnum)`.
    -   **Resource IDs**: Dataset and Table IDs are strictly validated via regex (`^[\w-]+$`) and length constraints.
    -   **Unified Types**: Uses `SCHEMA_DEFINITION` for structures and `ROWS` for data blocks to ensure semantic consistency.
-   **Framework**: Built on **FastMCP**, which provides a high-level API for defining tools and automatically handles the SSE transport.
    -   `GET /sse`: Establishes the agent connection.
    -   `POST /messages`: Handles incoming JSON-RPC tool-call execution requests.
-   **Standardized Responses**: Every tool returns a `BaseResponse` containing:
    -   `execution_status`: Strictly reports `success` or `error`.
    -   `execution_message`: High-level summary of the result or detailed error trace.
-   **Transport**: Server-Sent Events (SSE). HTTP-based transport for high compatibility with modern agent frameworks.

## 🤝 Connection Guide for Agents

Your MCP-compatible agent will automatically discover the tools and their parameters.

1.  **Transport Protocol**: Server-Sent Events (SSE) over HTTP.
2.  **Endpoint URL**:
    *   **Local Testing**: `http://localhost:8080/sse`
    *   **Production**: `https://[CLOUD_RUN_SERVICE_URL]/sse`
3.  **Authentication**:
    *   **Locally**: Relies on `gcloud auth application-default login`.
    *   **Production**: Ensure the agent passes a valid Google ID Token if the service is secured.

## 🔐 Security & Authentication (Keyless Architecture)

This server relies on **Google Application Default Credentials (ADC)**. No JSON key files are required, adhering to zero-trust security best practices.

### 1. In Production (Cloud Run)
-   Create a Service Account with restricted BigQuery roles (e.g., `roles/bigquery.dataEditor`, `roles/bigquery.jobUser`).
-   Deploy Cloud Run specifying this service account:
    ```bash
    gcloud run deploy bigquery-mcp-server --image IMAGE_URL --service-account="[SA_EMAIL]"
    ```

### 2. Local Development (Impersonation)
Developers can impersonate the target service account:
```bash
gcloud config set auth/impersonate_service_account [SA_EMAIL]
gcloud auth application-default login
```

---

## 💻 Local Development

This project uses `uv` for dependency management with a unified `pyproject.toml` in the repository root.

1.  **Dependencies**: Sync the BigQuery specific group:
    ```bash
    uv sync --group mcp_bq
    ```
2.  **Environment**: Run `make gcloud-auth` to configure your project and credentials.
3.  **Run Server**: Start the server using the provided Makefile:
    ```bash
    make run-bq-mcp
    ```
4.  **Testing**: Run the modernized async test suite:
    ```bash
    make run-bq-tests
    ```