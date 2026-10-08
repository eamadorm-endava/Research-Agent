# Custom UI & Authentication Architecture Plan

## Overview
This document outlines the technical design and implementation plan to migrate the Research-Agent system from Gemini Enterprise to a custom UI (Cloud Run + IAP) with custom OAuth token management (Firestore) and GCS Signed URL uploads.

## 1. Technical Architecture & Constraints

### 1.1 Core Architecture
*   **UI Stack**: A **FastAPI** backend to handle API routing, Vertex AI Agent Engine streaming, and Signed URLs. A generic **Streamlit** frontend for the chat interface.
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
│   └── frontend/                       # Streamlit UI assets (Tool Accordion, Auth Buttons)
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

## Minimal deployment corrections

- Keep `mcp-agent-vpc` and load-balancer IP `136.81.113.202`.
- Shared apply runs Terraform 1.12.2 in Cloud SDK so the existing provisioner has
  `bq` and Bash. The original model/resource/state handling is retained.
- Enable Private Google Access on the app subnet and use ALL_TRAFFIC frontend
  egress. The existing proxy-only subnet was imported into the remote GCS state using
  `terraform import`; it remains declared as a resource with no import block.
- IAP service identity is created before invoker IAM; serverless load-balancer
  backends use no health checks. `/api/*` routes reach the appropriate backend.
- The backend points at the existing production OSIRIS resource
  `projects/1051281656239/locations/us-central1/reasoningEngines/5233147857510334464`.
  Test UI uses that same agent; no new test-agent lifecycle is introduced.
- Test service deployments carry the necessary URL, network, OAuth secrets,
  Firestore and identity settings. Deploy the backend before the frontend on
  initial setup, as the frontend reads the backend URL.
- IAP assertions are verified before using user identity. OAuth transactions
  validate expiring, browser/user/provider-bound state and PKCE where supported.
  Cookie names and paths are literals for each provider (CodeQL alert #10).
- Retain the existing Streamlit layout and streaming flow. Remove the unwritable
  debug file, use public OAuth popup URLs and display stream failures correctly.

Register callbacks on both public domains for the existing OAuth clients, and
point both domain A records to `136.81.113.202`. The group `osiris_app_users@endava.com` configured
in `iap_accessor` is granted site access. The deployer needs `roles/iap.admin`
for these access bindings; bootstrap and frontend CD include that permission.

Verification: `make test-ui`, Terraform fmt/validate for shared resources,
gateway and both UI stacks. Deployment still uses the existing individual
pipelines. Uploads remain the original placeholder; additional features,
refresh locks, caching, CI orchestration and broad refactors are
outside this correction.


## Repository practice checks

The existing remote backend is retained at
`gs://prd-endava-ge-prod-01-2u00-1-terraform-state/terraform/state/agent-gateway-resources`.
The proxy-only subnet import was executed successfully there. No Terraform import
blocks or new discovery scripts are used. `make import-gateway-proxy-subnet` wraps
initialization and the import command for this existing environment.

Shared apply uses the exact Terraform 1.12.2 binary copied from the init container
into `/workspace/terraform-bin`, together with its trusted CA bundle. Cloud SDK
supplies Bash and `bq`; `SSL_CERT_FILE` selects that bundle for Terraform's HTTPS
connections. No Python installer or Terraform download is needed.
Each build step has one `args` list.

Trigger source filters omit tests, `pyproject.toml` and `uv.lock`. Cookie metadata
is selected from a fixed dictionary; internal helpers return named dictionaries.
Configuration fields use Pydantic `Annotated`/`Field`, provider requests have
bounded timeouts, and logs do not include tokens or full agent events. Backend
CORS permits only the configured public origin. HSTS, nosniff and CSP are set;
the OAuth close-window script is allowed by its exact CSP hash. SlowAPI supplies
the application-level request limit required by `.agents/rules/cybersecurity-guide.md`.

Use feature dependency groups for Python execution:

```bash
make test-ui
make lint-ui
make validate-ui-terraform
uv run --group backend --group dev python -m your.backend.module
uv run --group frontend python -m your.frontend.module
```

This is a correction of the existing UI, not a new deployment feature. The
existing GCS state naming and repository layout are retained rather than migrated;
no new infrastructure or broad CFF/module refactor is introduced. The existing
CFF service/load-balancer modules remain in use. Acceptance in GCP and merging
PR #292 are separate release steps; unit checks do not claim they have happened.

## Sequential connection card

The existing chat authentication flow now shows one compact, neutral card:
`Authentication Required: Google Workspace Connection`. A user click opens a
named popup for that provider only. After each successful OAuth exchange, the
existing CSP-authorized script closes the popup. The next provider's OAuth flow
starts only when the user clicks its connection card; callbacks never redirect
automatically into another provider's consent flow.
Browser settings can affect whether a requested popup appears as a window or tab.

`GET /api/auth/status` checks credentials for the verified IAP user and returns
only provider names. A Streamlit fragment polls it every three seconds while
consent is pending. After confirmation, it shows a running `Loading…` indicator
for one polling interval before displaying the next connection card. The card
advances only on confirmed server state; canceled
consent or closing a window never marks a connection ready. Once no providers
remain, the original chat question resumes without a Continue button or a second
user message. A 401 still requires reloading the access session.

The implementation is limited to the OAuth router/state, connection response
schema, frontend `authentication.py`/chat integration, and their regression
tests. No GCP resources or additional Python packages are introduced. The
frontend requires Streamlit 1.57 or newer for `st.iframe`, and keeps its existing
locked version. Service tokens and IAP assertions stay separate; signatures,
audiences, expiry, state, PKCE and browser/user binding remain enforced. The
previous multi-provider chaining flag is no longer used, including for older
pending transactions. Each provider requires a separate user-initiated login.
