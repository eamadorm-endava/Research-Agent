# MCP Tools & Dual Authentication process Architecture

This document provides a detailed overview of the Model Context Protocol (MCP) tools implemented in this repository and breaks down the dual-layer authentication model used to securely manage communications between the AI Agent, the MCP Servers, and Google Cloud APIs.

---

## 1. MCP Tools Overview

Model Context Protocol (MCP) servers act as highly-specialized executors that allow AI Agents to interact securely with external ecosystems. Encapsulating complex integrations ensures that agents stay lightweight, avoiding overly complicated dependencies directly in the agent's core codebase.

The current system implements the following MCP servers:
* **BigQuery MCP Server**: Executes complex analytical queries and retrieves relational dataset schemas.
* **Cloud Storage (GCS) MCP Server**: Interacts with cloud buckets to read or list raw blobs.
* **Google Drive MCP Server**: A workspace-focused connector that allows users to interact with Documents, Sheets, PDFs, and general file listings.

---

## 2. The Dual Authentication Architecture

When a user submits a query that requires executing an MCP tool (such as reading a private drive file), the network traffic traverses varying trust boundaries. To maintain data privacy, the system utilizes a **dual authentication architecture**:

1. **Service-to-Service Security** (Agent to Cloud Run)
2. **End-User Privacy** (MCP Server to Drive API)

### Layer 1: Agent to MCP Server (Cloud Run Authentication)

The AI Agent runs in Vertex AI. To securely send a request to the remote MCP Servers—which run as protected Cloud Run services—the agent must prove its service identity.

**How it works (`agent/core_agent/utils/security.py`):**
1. **Token Retrieval**: The Agent uses the `get_id_token()` utility, which dynamically contacts the locally available GCP Metadata server (or local Application Default Credentials in dev mode) to retrieve a valid OpenID Connect (OIDC) ID token. 
2. **Audience Scoping**: This token is strictly scoped to the exact `audience_url` of the target MCP server for enhanced security.
3. **HTTP Transport**: Using ADK's `McpToolset` and `header_provider` injection, the agent constructs an HTTP request including the header:
   ```http
   X-Serverless-Authorization: Bearer <cloud-run-id-token>
   ```
4. **Validation**: The Cloud Run IAM proxy intercepts the request. If the Agent's Service Account lacks the `roles/run.invoker` role for that specific server, the request is blocked.

### Layer 2: MCP Server to Target APIs (OAuth for Google Drive)

While Cloud Run proves *who the agent is*, it does not define *what the end-user is allowed to see*. The Google Drive MCP Server must impersonate the actual end-user interacting with Gemini Enterprise, fully respecting the user's workspace sharing restrictions.

**How it works (`mcp_servers/google_drive/`):**
1. **Delegated Token Flow**: Gemini Enterprise secures user consent (via OAuth 2.0 flow) and issues a delegated access token. The Agent retrieves this from its context (via `GEMINI_DRIVE_AUTH_ID`) using the `get_ge_oauth_token` helper and forwards it downstream via the standard `Authorization` header.
2. **Authorized Redirect URIs**: Security is strictly enforced at the GCP level. Only redirect URIs explicitly allowed in the GCP console for the OAuth Client ID are able to successfully complete the authentication flow and obtain OAuth tokens for Drive connections.

3. **Context Persistence (`mcp_server.py`)**: As the request enters the Drive MCP Server, a `HeaderCaptureMiddleware` captures the inbound HTTP headers directly into Python's `contextvars`. This allows FastMCP functions to transparently access the calling user's token outside of strict parameter definitions.
4. **Validation & Credential Building (`drive_client.py`)**: 
   * The server extracts the `x-drive-access-token`.
   * The token is rigorously validated against Google's Token Info API (`https://www.googleapis.com/oauth2/v3/tokeninfo`) to ensure it corresponds to the correct client environment and has the essential scopes (e.g., `drive.readonly`).
   * A `google.oauth2.credentials.Credentials` object is constructed exclusively using this delegated access token.
5. **API Execution**: All Google Drive API clients (v3 for Drive, v1 for Docs) are built using these User Credentials. If the user session lacks an active token or the needed scopes, an `AuthenticationError` is caught, returning an OAuth login prompt to the user interface.