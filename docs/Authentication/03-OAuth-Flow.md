# Detailed OAuth 2.0 Flow & Token Lifecycle

This document provides a technical deep-dive into how the Per-User OAuth 2.0 flow is managed within the AI Agent Architecture. It specifically breaks down the responsibilities at each layer: the ADK Framework, the Frontend Clients (UI Dev Mode & Gemini Enterprise), and the MCP Servers.

## 1. The ADK Layer (The Trigger)

The Agent Development Kit (ADK) sits at the core of the architecture. It orchestrates the LLM, the tools (MCPs), and the session state.

1. **Tool Invocation**: During a user session, the LLM determines it needs to call a secure tool (e.g., the Google Drive MCP).
2. **Missing Token Detection**: The ADK configuration specifies that this tool requires an OAuth 2.0 credential. It attempts to resolve the `AuthCredential` from the current session context.
3. **Event Emission**: If no valid token is present in the session, the ADK immediately pauses the LLM execution. It yields a special system event back to the client application: `adk_request_credential`.
4. **Payload**: This event contains the necessary `auth_config`, including the Client ID, Requested Scopes, and the Authorization URL.

> **Crucial Concept**: The ADK framework *does not* manage the UX, browser redirects, or persistent databases. It simply acts as a circuit breaker, pausing execution and requesting credentials from whatever client is running it.

## 2. The Frontend Layer (Handling Consent & Storage)

How the `adk_request_credential` event is handled depends entirely on the frontend client executing the ADK session.

### A. Local UI Development (`make run-ui-agent`)

When developers test agents locally using the built-in React UI, the ADK UI backend serves as the client.

1. **Interception**: The UI backend intercepts the `adk_request_credential` event via the FastAPI `/run_sse` stream.
2. **Rendering UX**: The React frontend renders a native "Login with Google" prompt directly within the chat interface, using the URL provided in the eventpayload.
3. **Consent & Callback**: The developer clicks the link, authorizes the app in Google, and is redirected to a local callback handler (or manually pastes a code if running strictly headless CLI).
4. **Token Exchange**: The local UI backend exchanges the authorization code for an **Access Token** and a **Refresh Token**.
5. **Storage**: In local dev mode, these tokens are typically held securely in-memory for the duration of the server session or briefly cached in a local temp file strictly bound to the dev environment.
6. **Resumption**: The UI backend resumes the ADK session, injecting the newly acquired tokens into the context.

### B. Production Deployment (Gemini Enterprise)

When deployed to Google Cloud, Vertex AI Agent Engine and Gemini Enterprise act as the client.

1. **Pre-configuration**: Administrators must first register an **Authorization Resource** in Gemini Enterprise. This configuration holds the production OAuth Client ID, Secret, and the pre-approved scopes for the agent.
2. **Interception**: Agent Engine intercepts the `adk_request_credential` event.
3. **Native UX**: Gemini Enterprise pauses the user's chat and presents a native, managed consent prompt.
4. **Consent & Callback**: The user authorizes the application. The redirect goes to a secure, google-managed domain (e.g., `vertexaisearch.cloud.google.com/static/oauth/oauth.html`).
5. **Storage & Management**: Gemini Enterprise securely stores the resulting Access Token and Refresh Token within its managed infrastructure, cryptographically tied to the user's identity. 
6. **Lifecycle**: Gemini Enterprise completely obfuscates the token lifecycle. It handles refreshing expired access tokens transparently in the background using the stored refresh token.

## 3. The Execution Layer (Using the Token)

Once the client (Local UI or Gemini Enterprise) has provided the valid token back to the ADK session, the execution resumes.

1. **Context Injection**: The `AuthCredential` is injected into the ADK Session context.
2. **Header Attachment**: As the ADK framework constructs the HTTP request to the target MCP Server, the underlying `streamable_http_client` (or equivalent transport) inspects the credential.
3. **Bearer Token Generation**: The `OAuthClientProvider` extracts the active **Access Token** and attaches it to the request as standard headers:
   *  `Authorization: Bearer <access_token>`

## 4. The MCP Layer (Validation)

The MCP Server is the final destination. Its primary responsibility is exposing tools and validating access.

1. **Stateless Nature**: **The MCP Server is entirely stateless regarding authentication.** It does not have a `/auth` endpoint, it does not receive authorization codes to exchange, and it does not connect to a database (like Firestore) to look up user tokens.
2. **Stateless Validation**: When an incoming request arrives, the MCP server extracts the Bearer token from the `Authorization` header.
3. **JWT Verification**: It cryptographically verifies the signature of the access token using Google's public JWKS (JSON Web Key Set), ensuring it hasn't expired and hasn't been tampered with.
4. **Scope Verification**: It verifies that the token contains the specific scopes required to execute the requested tool (e.g., verifying `https://www.googleapis.com/auth/drive.readonly` is present).
5. **API Forwarding**: If valid, the MCP Server uses this exact same access token to authenticate its outward-bound calls to the target Google Cloud/Workspace APIs.

---

### Summary Diagram

```mermaid
sequenceDiagram
    participant User
    participant App as Frontend (Local UI / Gemini UI)
    participant Agent as ADK Core
    participant MCP as MCP Server
    participant Google as Google APIs

    Note over Agent: ADK detects missing auth
    Agent-->>App: Yield `adk_request_credential`
    App->>User: Display Auth Prompt
    User->>Google: Grant Consent
    Google-->>App: Auth Code
    Note over App: App manages Token Exchange & Storage
    App->>App: Exchange code for Tokens
    App->>Agent: Resume Agent with Tokens
    Agent->>MCP: Tool Call + 'Authorization: Bearer <Token>'
    Note over MCP: Stateless signature & scope validation
    MCP->>Google: GCP API Request with Token
    Google-->>MCP: API Response
    MCP-->>Agent: Tool Result
```

## 5. References & Further Reading

For authoritative documentation on these features, please consult the official guides:
* **ADK Agent Credentials Details**: [Authenticating with Tools (Handling the Interactive OAuth Flow)](https://google.github.io/adk-docs/tools-custom/authentication/#2-handling-the-interactive-oauthoidc-flow-client-side)
* **Auth Resources (Gemini Enterprise)**: [Configure authorization details for ADK agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent#configure-authorization-details)
* **Agent Registration (Gemini Enterprise)**: [Register an ADK agent with Gemini Enterprise](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent#register-an-adk-agent)
