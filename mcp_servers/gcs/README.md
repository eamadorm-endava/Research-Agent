# Cloud Storage MCP Server

This server is built using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) and the Python MCP SDK `FastMCP` stack, aligned with `mcp_servers/big_query`.

## 🌟 Server Capabilities

The MCP Server wraps the `google-cloud-storage` client and exposes the following tools to any compatible AI Agent:

-   **`create_bucket`**: Create new buckets in a specified location.
-   **`update_bucket_labels`**: Manage metadata and tagging for buckets.
-   **`upload_object`**: Upload data to GCS. Supports plain text, binary sequences (bytes), or streaming from local file paths with automatic MIME-type detection.
-   **`read_object`**: Download an object's contents securely into the agent's memory (attempts UTF-8 decoding, falls back to raw bytes for binary files).
-   **`update_object_metadata`**: Update metadata, including the crucial `content_type` attribute.
-   **`list_objects`**: List files in a bucket, with support for prefix filtering (simulating directory structures), essential for agent discovery and navigation.
-   **`list_buckets`**: List buckets available in the current project, with optional bucket-name prefix filtering.
-   **`delete_object`**: Safely remove files.

## 🛠️ Architecture

-   **Server Stack**: `FastMCP` (`mcp.server.fastmcp.FastMCP`) with asynchronous tool functions.
-   **Transport**: `streamable-http`, matching the BigQuery MCP implementation style.
-   **Execution Model**: blocking SDK calls are executed via `asyncio.to_thread` to keep the MCP server responsive.

## 🤝 Connection Guide for Agents

Because this server uses MCP, your agent auto-discovers tools and schemas after connecting.

1.  **Transport Protocol**: `streamable-http`
2.  **Endpoint URL**:
    *   **Local Testing**: `http://localhost:8080/mcp`
    *   **Production (Cloud Run)**: `https://[CLOUD_RUN_SERVICE_URL]/mcp`
3.  **Authentication**:
    *   **MCP OAuth**: The server expects `Authorization: Bearer <delegated-user-oauth-access-token>` and validates it through MCP auth middleware.
    *   **Cloud Run IAM**: If service ingress is protected, the caller also needs `X-Serverless-Authorization: Bearer <google-id-token>` for Cloud Run invocation.

## 🔐 Security & Authentication (Delegated User Access)

This MCP server relies on a **delegated end-user OAuth access token** propagated by ADK/Gemini Enterprise through the MCP `Authorization` header. No JSON key files are required.

### ADR Alignment
- This implementation follows the repository authentication strategy ADR for delegated per-user OAuth token propagation and stateless MCP token validation.
- The GCS server uses MCP middleware token verification, then builds the downstream `google-cloud-storage` client dynamically per request with delegated user credentials.

### Key Benefits
- **Least-Privilege Data Access**: Bucket and object operations run with the requesting user's GCS IAM permissions, not a broad backend identity.
- **Safer Failure Mode**: Unauthorized attempts return `execution_status="error"` with `Permission Denied` or `Object not found` instead of object data or bucket mapping leakage.
- **Reduced Credential Exposure Risk**: Tokens are handled through MCP auth context and are not logged by the tool handlers.

Here is how you control and restrict the server's access:

### 1. In Production (Cloud Run)
When deploying to Cloud Run, you use an **Attached Service Account** for service invocation/runtime only:
-   Create a target Service Account in GCP: `gcs-mcp-sa@your-project.iam.gserviceaccount.com`.
-   Grant this specific SA only the roles needed to run the server or call downstream platform services. Bucket/object authorization should come from the delegated user token.
-   Deploy the Cloud Run service specifying this Service Account flag:
    ```bash
    gcloud run deploy gcs-mcp-server --image XYZ --service-account="gcs-mcp-sa@your-project.iam.gserviceaccount.com"
    ```
-   The agent also needs `roles/run.invoker` permission if Cloud Run ingress is protected.

### 2. Local Development
For end-to-end auth parity with Gemini Enterprise, send a valid user OAuth access token as `Authorization: Bearer <token>` when invoking `/mcp`.

If you are only validating Cloud Run ingress, also include an ID token in `X-Serverless-Authorization`.

### 3. Two-Profile E2E Validation (Required)
Validate with two distinct user profiles to confirm IAM boundaries:
- **Profile A (authorized)**: user has `roles/storage.objectViewer` (or stronger) on target bucket.
- **Profile B (unauthorized)**: user does not have read/list access on same bucket.

Expected outcomes:
- Profile A: `list_objects`/`read_object` return `execution_status="success"`.
- Profile B: requests return `execution_status="error"` and include `Permission Denied` or `Object not found`.

---

## 🚀 Deployment Options in Google Cloud

Because this MCP Server uses streamable HTTP transport, deployment on Google Cloud is straightforward and scalable. There are two primary deployment patterns:

### Option 1: Google Cloud Run (Recommended for Scalability)

Deploying as a standalone Cloud Run service provides a scalable, serverless endpoint that multiple agents or applications can connect to.

**Pros**:
-   **Auto-scaling**: Scales to zero when not in use, and scales up horizontally under load.
-   **Security**: Can be protected by Cloud IAM (requiring the Agent to pass an identity token) or Identity-Aware Proxy (IAP).
-   **Centralized**: Can be updated independently of the agents using it.

**How to Deploy**:
The repository includes a `Dockerfile` and `cloudbuild.yaml` optimized for Cloud Run. Note that the Docker build context **must be the root of the repository** so it can access the master `pyproject.toml`.
1. Ensure the shared Artifact Registry repository and Terraform-managed Cloud Run infrastructure already exist.
2. Run Cloud Build from the root of the repository to create the image and deploy to Cloud Run:
   ```bash
    gcloud builds submit --config=mcp_servers/gcs/cloudbuild.yaml .
   ```
3. **Agent Integration**: Once deployed, configure your Agent Development Kit (ADK) agent to use the resulting Cloud Run URL (e.g., `https://gcs-mcp-xyz.a.run.app/mcp`).

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
2.  **Authentication**: Use a delegated user OAuth access token for end-to-end testing of authorization behavior.
3.  **Run Server**: Start the MCP server locally from the repository root:
    ```bash
    uv run --group mcp_gcs python -m mcp_servers.gcs.app.main --host localhost --port 8080
    ```
4.  **Testing**: Run unit tests using `pytest`:
    ```bash
    uv run --group mcp_gcs pytest mcp_servers/gcs/tests/
    ```

### Terminal MCP Smoke Test (No Browser)

You can validate the MCP protocol handshake and a real tool call from terminal only.

1. Start the server in one terminal:
    ```bash
    make run-gcs-mcp-locally
    ```
2. Run a smoke test from another terminal (replace bucket/prefix):
    ```bash
    make run-gcs-mcp-smoke BUCKET=my-gcs-bucket PREFIX=docs/
    ```

   Optional bucket prefix filter:
   ```bash
   make run-gcs-mcp-smoke BUCKET=my-gcs-bucket PREFIX=docs/ BUCKET_PREFIX=my-
   ```

This executes:
- `initialize`
- `notifications/initialized`
- `tools/list`
- `tools/call` for `list_buckets`
- `tools/call` for `list_objects`

You can also call `list_buckets` with an optional prefix using your MCP client once the server is running.

If you prefer direct command usage without `make`:
```bash
uv run --group mcp_gcs python mcp_servers/gcs/scripts/mcp_smoke_test.py --endpoint http://localhost:8080/mcp --bucket mikes-bucket --prefix docs/ --bucket-prefix my- 
```
