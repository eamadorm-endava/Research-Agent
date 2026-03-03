# Cloud Storage Connector (MCP Server)

This connector is built using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) and Python's FastAPI. It provides a secure, modular server that exposes Google Cloud Storage (GCS) operations as tools for AI Agents.

## 🌟 Server Capabilities

The MCP Server wraps the `google-cloud-storage` client and exposes the following tools to any compatible AI Agent:

-   **`create_bucket`**: Create new buckets in a specified location.
-   **`update_bucket_labels`**: Manage metadata and tagging for buckets.
-   **`upload_object`**: Upload data to GCS. Supports plain text, binary sequences (bytes), or streaming from local file paths with automatic MIME-type detection.
-   **`read_object`**: Download an object's contents securely into the agent's memory (attempts UTF-8 decoding, falls back to raw bytes for binary files).
-   **`update_object_metadata`**: Update metadata, including the crucial `content_type` attribute.
-   **`list_objects`**: List files in a bucket, with support for prefix filtering (simulating directory structures), essential for agent discovery and navigation.
-   **`delete_object`**: Safely remove files.

## 🛠️ Architecture

-   **Transport**: Server-Sent Events (SSE). This HTTP-based transport makes the server highly compatible with cloud-native deployments and avoids the complexities of maintaining persistent WebSocket connections in stateless environments.
-   **Routing**: Built on `FastAPI`.
    -   `GET /sse`: Establishes the agent connection.
    -   `POST /messages`: Handles incoming JSON-RPC tool-call execution requests.

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
The repository includes a `Dockerfile` and `cloudbuild.yaml` optimized for Cloud Run.
1. Configure `cloudbuild.yaml` with your GCP Project and preferred Google Artifact Registry region.
2. Run Cloud Build to create the image and deploy to Cloud Run:
   ```bash
   gcloud builds submit --config=cloudbuild.yaml
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

1.  **Virtual Environment**: Ensure dependencies are installed `pip install -r requirements.txt`.
2.  **Authentication**: Run `gcloud auth application-default login` to use your local credentials, OR set `export GCP_SERVICE_ACCOUNT_PATH="/path/to/key.json"`.
3.  **Run Server**: Start the FastAPI server locally:
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
    ```
4.  **Testing**: Run unit tests (with mocked clients) using `pytest tests/`.
