# Custom UI & Authentication Architecture Plan

## Overview
This document outlines the technical design and implementation plan to migrate the Research-Agent system from Gemini Enterprise to a custom UI (Cloud Run + IAP) with custom OAuth token management (Firestore) and GCS Signed URL uploads.

## 1. Technical Architecture & Constraints

### 1.1 Core Architecture
*   **UI Stack**: A **FastAPI** backend to handle API routing, Vertex AI Agent Engine streaming, and Signed URLs. A generic **React/Next.js** frontend for the chat interface.
*   **Token Storage**: **Firestore** (Native Mode) for secure, scalable, and serverless storage of user refresh tokens.
*   **Agent Execution**: The custom UI will invoke the agent remotely using the `vertexai.agent_engines` SDK to stream responses and tool execution (`async_stream_query`).

### 1.2 UX/UI Specific Requirements
*   **Collapsible Tool Logs**: When the agent executes tools, the frontend will group these events into an expandable/collapsible accordion (similar to the Gemini app).
    *   On `FunctionCall`: Display the function name with a loading spinner.
    *   On `FunctionResponse`: Replace the spinner with a checkmark.
*   **In-Stream Authentication**:
    *   Instead of a dedicated settings page, authentication is triggered in the chat.
    *   When the user sends their first message, the backend will verify if the required tokens exist in Firestore.
    *   If tokens are missing, the backend will pause agent execution and stream an `AUTH_REQUIRED` event to the frontend, specifying *which* data sources are missing (Google, Microsoft, Atlassian).
    *   The frontend will render specific "Authenticate [Source]" buttons directly in the chat stream (e.g., "Authenticate Microsoft", "Authenticate Google", "Authenticate Atlassian").
    *   Each button will trigger its respective OAuth flow. Once authenticated, the user can proceed with their request.

### 1.3 Folder Structure & File Manifest
```text
Research-Agent/
├── ui/
│   ├── backend/
│   │   ├── main.py                     # FastAPI entry point
│   │   ├── routers/
│   │   │   ├── chat.py                 # Agent streaming & AUTH_REQUIRED check
│   │   │   ├── upload.py               # GCS Signed URL generator
│   │   │   └── oauth.py                # Provider-specific OAuth callback handlers
│   │   └── requirements.txt
│   └── frontend/                       # React / Web UI assets (Tool Accordion, Auth Buttons)
├── agent/core_agent/security/
│   ├── auth.py                         # EDITED: Remove GE logic
│   └── token_store.py                  # NEW: Firestore integration for tokens
├── agent/core_agent/builder/
│   └── mcp_factory.py                  # EDITED: Use token_store.py instead of GE Context
├── terraform/
│   ├── shared_resources/
│   │   └── firestore.tf                # NEW: Firestore database provisioning
│   └── ui_resources/                   # NEW: IAP, Load Balancer, and Cloud Run modules
└── docs/modules/
    └── custom_ui_auth.md               # This document
```

---

## 2. Implementation Plan (GitHub Issues)

The execution will follow the mandatory two-issue strategy (Part A: Prototyping, Part B: Deployment).

### Issue #1: [Part A] Implement Custom OAuth Token Storage (Firestore)
> **User Story**
> - **As a** System Architect
> - **I want to** establish a custom token storage mechanism using Firestore
> - **So that** we can securely store and refresh 3rd-party OAuth tokens independently of Gemini Enterprise.
>
> ## Technical Specifications & Constraints
> - **Scope**: `agent/core_agent/security/token_store.py`
> - **Logic**: Implement a Firestore client to store and retrieve `refresh_token` and `access_token` objects keyed by `user_id` (email) and `provider` (google, microsoft, atlassian).
> - **Validation**: Implement a script to test saving and retrieving tokens.
>
> ## Acceptance Criteria
> - [ ] Firestore utility class is created with `save_token` and `get_valid_access_token` methods.
> - [ ] `get_valid_access_token` automatically refreshes expired tokens.

### Issue #2: [Part A] Refactor Agent Security & MCP Factory
> **User Story**
> - **As an** AI Agent
> - **I want to** retrieve 3rd-party credentials from Firestore instead of GE Context
> - **So that** I can continue accessing MCP servers in the new custom UI environment.
>
> ## Technical Specifications & Constraints
> - **Scope**: `agent/core_agent/security/auth.py`, `agent/core_agent/builder/mcp_factory.py`
> - **Logic**: Deprecate `get_ge_oauth_token`. Update `mcp_factory.py` to inject tokens fetched via the new `token_store.py` based on the `user_id` present in the `ReadonlyContext`.
>
> ## Acceptance Criteria
> - [ ] MCP servers successfully receive Bearer tokens from Firestore during agent execution.

### Issue #3: [Part A] Develop UI Backend (Streaming, In-Stream Auth, Signed URLs)
> **User Story**
> - **As a** User
> - **I want to** have a backend that handles my file uploads, checks my auth status, and streams the agent's thought process
> - **So that** I can interact with the agent in real-time.
>
> ## Technical Specifications & Constraints
> - **Scope**: `ui/backend/`
> - **Logic**: 
>   - Parse `X-Goog-Authenticated-User-Email` header for `user_id`.
>   - `/api/chat`: Check Firestore for tokens. If missing, yield an `AUTH_REQUIRED` SSE event containing the list of missing providers (e.g., `["microsoft", "google"]`). Otherwise, connect to Vertex AI and stream `FunctionCall` and `FunctionResponse` events.
>   - `/api/auth/{provider}`: Handle individual OAuth flows for microsoft, google, and atlassian.
>
> ## Acceptance Criteria
> - [ ] Chat endpoint streams `AUTH_REQUIRED` with missing providers array if tokens are missing.
> - [ ] Chat endpoint streams `FunctionCall` and text chunks when authenticated.

### Issue #4: [Part A] Develop UI Frontend (Chat, Tool Accordions, Auth Buttons)
> **User Story**
> - **As a** User
> - **I want to** see a clean chat interface with collapsible tool logs and in-stream auth buttons
> - **So that** I can easily monitor what the agent is doing and authenticate per data source when needed.
>
> ## Technical Specifications & Constraints
> - **Scope**: `ui/frontend/`
> - **Logic**: 
>   - **Tools Accordion**: Render `FunctionCall` events with a spinner. Update to a checkmark when `FunctionResponse` is received. Group them in a collapsible UI block.
>   - **Auth Buttons**: Listen for `AUTH_REQUIRED` stream event and render separate "Authenticate [Provider]" buttons inline based on the missing providers array.
>
> ## Acceptance Criteria
> - [ ] Tool executions show spinner -> checkmark in a collapsible tab.
> - [ ] Distinct provider authentication buttons appear in chat and redirect to `/api/auth/{provider}`.

### Issue #5: [Part B] Provision Firestore Infrastructure
> **User Story**
> - **As a** DevOps Engineer
> - **I want to** provision a Firestore database using Terraform
> - **So that** the application has a production-ready database for tokens.
>
> ## Technical Specifications & Constraints
> - **Scope**: `terraform/shared_resources/firestore.tf`
> - **Logic**: Use Cloud Foundation Fabric (CFF) modules to provision a Native Mode Firestore database.

### Issue #6: [Part B] Provision UI Infrastructure (Cloud Run, IAP, LB)
> **User Story**
> - **As a** DevOps Engineer
> - **I want to** deploy the Custom UI behind an IAP-protected Global Load Balancer
> - **So that** enterprise users can access it securely without a custom login screen.
>
> ## Technical Specifications & Constraints
> - **Scope**: `terraform/ui_resources/`
> - **Logic**: Provision Cloud Run service, Global External HTTP Load Balancer, IAP enablement, and SSL certificates.
