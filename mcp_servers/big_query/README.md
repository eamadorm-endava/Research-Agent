# BigQuery Connector (MCP Server)

This connector is built using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) and Python's FastAPI. It provides a secure, modular server that exposes Google Cloud BigQuery operations as tools for AI Agents.

## 🌟 Server Capabilities

The MCP Server wraps the `google-cloud-bigquery` client and exposes the following tools to any compatible AI Agent:

-   **`create_dataset`**: Create new BigQuery datasets.
-   **`create_table`**: Create new tables with specified schemas.
-   **`execute_query`**: Run read-only standard SQL queries against BigQuery data. Converts structs and arrays into safe JSON constructs.
-   **`get_table_schema`**: Retrieve the field schema of a specific table.
-   **`list_tables`**: List all tables in a given dataset for agent discovery.
-   **`add_row`**: Stream insert new records into an existing table.

## 🛠️ Architecture

-   **Transport**: Server-Sent Events (SSE). This HTTP-based transport makes the server highly compatible with cloud-native deployments and avoids the complexities of maintaining persistent WebSocket connections in stateless environments.
-   **Routing**: Built on `FastAPI`.
    -   `GET /sse`: Establishes the agent connection.
    -   `POST /messages`: Handles incoming JSON-RPC tool-call execution requests.

## 🤝 Connection Guide for Agents

Because this server uses the Model Context Protocol (MCP), your agent will automatically self-discover all the available GCS tools (like `upload_object` or `list_objects`) and their schemas upon connecting. You only need to provide the agent framework with three details:

1.  **Transport Protocol**: Server-Sent Events (SSE) over HTTP.
2.  **Endpoint URL**: The exact URL pointing to the `/sse` route.
    *   **Local Testing**: `http://localhost:8080/sse`
    *   **Production (Cloud Run)**: `https://[CLOUD_RUN_SERVICE_URL]/sse` *(Placeholder: Update after deployment)*
3.  **Authentication**:
    *   **Locally**: None required. Relies on the host's `gcloud auth application-default login`.
    *   **Production**: If Cloud Run is secured via IAM natively, the agent making the HTTP request must attach an `Authorization: Bearer <Google_ID_Token>` header to the `/sse` request.

## 🔐 Security & Authentication (Keyless Architecture)

This MCP server relies entirely on **Google Application Default Credentials (ADC)**. We strictly avoid long-lived JSON key files to adhere to zero-trust security best practices.

Here is how you control and restrict the server's access:

### 1. In Production (Cloud Run)
When deploying to Cloud Run, you use an **Attached Service Account**:
-   Create a target Service Account in GCP: `gcs-mcp-sa@your-project.iam.gserviceaccount.com`.
-   Grant this specific SA the exact roles it needs (e.g., `roles/storage.objectAdmin` on a *specific* bucket via IAM conditions).
-   Deploy the Cloud Run service specifying this Service Account flag:
    ```bash
    gcloud run deploy gcs-mcp-server --image XYZ --service-account="gcs-mcp-sa@your-project.iam.gserviceaccount.com"
    ```
-   The MCP server automatically inherits these restricted permissions natively via the GCP metadata server. No keys required.

### 2. Local Development (Impersonation)
To test restricted permissions locally without downloading a JSON key, developers can **impersonate** the target Service Account using short-lived tokens:

1.  Ask your GCP admin to grant your personal user account the `roles/iam.serviceAccountTokenCreator` role on the target Service Account.
2.  Configure your local `gcloud` to impersonate it:
    ```bash
    gcloud config set auth/impersonate_service_account gcs-mcp-sa@your-project.iam.gserviceaccount.com
    gcloud auth application-default login
    ```
3.  When you run the MCP server locally, it will automatically request short-lived tokens on behalf of `gcs-mcp-sa`, strictly mirroring production permissions.

---

## 🚀 Deployment Options in Google Cloud

Because this MCP Server uses HTTP/SSE, deployment on Google Cloud is straightforward and scalable. There are two primary deployment patterns:

### Option 1: Google Cloud Run (Recommended for Scalability)

Deploying as a standalone Cloud Run service provides a scalable, serverless endpoint that multiple agents or applications can connect to.

**Pros**:
-   **Auto-scaling**: Scales to zero when not in use, and scales up horizontally under load.
-   **Security**: Can be protected by Cloud IAM (requiring the Agent to pass an identity token) or Identity-Aware Proxy (IAP).
-   **Centralized**: Can be updated independently of the agents using it.

**How to Deploy**:
The repository includes a `Dockerfile` and `cloudbuild.yaml` optimized for Cloud Run. Note that the Docker build context **must be the root of the repository** so it can access the master `pyproject.toml`.
1. Configure `cloudbuild.yaml` with your GCP Project and preferred Google Artifact Registry region.
2. Run Cloud Build from the root of the repository to create the image and deploy to Cloud Run:
   ```bash
   gcloud builds submit --config=mcp_servers/gcs/cloudbuild.yaml .
   ```
3. **Agent Integration**: Once deployed, configure your Agent Development Kit (ADK) agent to use the resulting Cloud Run URL (e.g., `https://gcs-mcp-xyz.a.run.app/sse`).

### Option 2: Vertex AI Tool / Extension

If you are using Google's Vertex AI Agent Builder or orchestration frameworks heavily embedded in the Vertex ecosystem, you can register this functionality directly as a Vertex AI Tool/Extension.

**Pros**:
-   **Native Integration**: Works seamlessly with Vertex AI reasoning engines and Gemini.
-   **Managed Auth**: Vertex AI handles the auth handshake if configured as an OpenAPI extension.

**How to Deploy**:
1. You still deploy the container to Cloud Run (as in Option 1) to host the actual execution logic.
2. You generate an OpenAPI specification (`openapi.yaml`) describing the `/messages` endpoints.
3. In the Google Cloud Console (Agent Builder -> Extensions), register a new Extension pointing to your Cloud Run url and your `openapi.yaml`. 
4. **Note**: As native MCP integration expands in Vertex AI, you may be able to register the SSE endpoint directly without the OpenAPI wrapper in the future.

---

## 💻 Local Development

This project uses `uv` for dependency management with a unified `pyproject.toml` in the repository root.

1.  **Dependencies**: From the root of the repository, sync the specific dependencies for this connector:
    ```bash
    uv sync --group mcp_gcs
    ```
2.  **Authentication**: Run `gcloud auth application-default login` to use your local credentials (or configure impersonation as described above).
3.  **Run Server**: Start the FastAPI server locally from the repository root:
    ```bash
    uv run --group mcp_gcs uvicorn mcp_servers.gcs.app.main:app --host 0.0.0.0 --port 8080 --reload
    ```
4.  **Testing**: Run unit tests using `pytest`:
    ```bash
    uv run --group mcp_gcs pytest mcp_servers/gcs/tests/
    ```
