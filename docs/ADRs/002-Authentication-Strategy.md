# ADR-002: Authentication Strategy for MCP Servers

**Status**: Accepted
**Date**: March 18, 2026
**Owner**: Security / Platform Engineering
**Related Systems**: Google Drive, Google Calendar, BigQuery, GCS, Gemini Enterprise, MCP Servers, IAM

## 1. Context

AI Agents running in Gemini Enterprise (via the ADK framework) connect to customized Model Context Protocol (MCP) servers to retrieve, create, or update enterprise data. As defined in [ADR-001: Data Privacy Strategy](001-Data-Privacy-Strategy.md), the primary privacy boundary relies on strict Identity and Access Management (IAM) controls: the AI Agent must only access data that the invoking end-user is explicitly authorized to access. 

Therefore, when the MCP server requests data from an underlying Google Cloud or Google Workspace API, it must securely propagate the identity of the user. We analyzed two predominant methods for achieving this identity propagation:

1. **Domain-Wide Delegation (DWD)**: A Google Cloud Service Account is granted authority by a Workspace Super Admin to impersonate any user within the organization. The MCP assumes this service account identity and requests scoped credentials on behalf of the invoking user.
2. **Per-User OAuth 2.0 (Individual Consent Flow)**: Each user individually authorizes the application via Google's OAuth 2.0 consent screen. The **ADK Agent (Client)** handles this in two ways:
    *   **Standard Flow**: The agent natively intercepts `adk_request_credential` events, pauses execution, and waits for the frontend to exchange tokens.
    *   **GE-Optimized Flow**: When running inside **Gemini Enterprise**, the platform provides a native UX flow and proactively injects the access token into the agent's context (`ctx.state`). The agent retrieves this via `get_ge_oauth_token()` and manually injects it into the MCP Tool headers. This bypasses the interactive framework events, leading to a faster and more stable execution.

## 2. Decision

We will use **Per-User OAuth 2.0 (Individual Consent Flow)** as the primary authentication strategy for MCP Servers connecting to GCP and Google Workspace APIs.

While Domain-Wide Delegation remains an option for specific, highly-controlled administrative workloads (if explicitly approved), standard user-facing AI capabilities will use the individual consent flow. 

## 3. Decision Drivers

This decision is based on the following drivers:

*   **High Barrier to Entry for DWD**: Domain-Wide Delegation requires intervention and explicit configuration by a Google Workspace Super Admin. This introduces significant operational friction and bottlenecks adoption for teams building or testing MCPs. 
*   **Broad Blast Radius of DWD**: A compromised DWD Service Account has access to all user data across the specified scopes in the entire Workspace domain. Limiting access requires highly granular organizational unit structures that are not always available.
*   **Support for Mixed Environments**: OAuth 2.0 works seamlessly for users outside of a centrally managed enterprise domain (e.g., external contractors or users on personal `@gmail.com` accounts), whereas DWD strictly requires a Workspace domain.
*   **Alignment with ADR-001**: Per-user OAuth robustly fulfills the mandate that access boundaries mirror exactly what the user can naturally access. By requiring explicit user consent, the privacy and authorization model remains fully intact and transparent to the user.
*   **Native UI Dev and Gemini Enterprise Support**: The Agent Development Kit (ADK) intrinsically handles interactive OAuth 2.0 flows via `adk_request_credential` events. When running the agent locally in **UI Development Mode** (`make run-ui-agent`), the built-in UI automatically intercepts these requests, provides the consent URL, and securely manages the resulting tokens in the local environment. When deployed, **Gemini Enterprise** natively intercepts these same events, presents the consent screen, and manages tokens via Authorization resources.
*   **Stateless MCP Architecture**: By shifting token lifecycle management to the frontends (ADK UI / Gemini Enterprise), the MCP Server is drastically simplified. It behaves purely as a stateless OAuth Resource Server (validating tokens without needing persistent databases or `/auth` endpoints).

## 4. Evaluated Options

### Option A. Domain-Wide Delegation (DWD)
**Pros:**
*   Requires zero interaction from the end-user (seamless inside Gemini Enterprise).
*   No requirement to manage persistent token stores (no refresh token lifecycle to track).

**Cons:**
*   Requires Workspace Super Admin manual approval.
*   Too high of a security risk (domain-wide access vs. scoped access).
*   Incompatible with personal/external Google accounts.

**Decision:** Rejected as the primary mechanism due to the permission bottleneck and risk profile.

### Option B. Per-User OAuth 2.0
**Pros:**
*   Excellent user-level isolation and strict security posture.
*   Easy for developers to set up without central IT bottlenecks.
*   Explicit user consent guarantees transparency.

**Cons:**
*   Requires an initial one-time authorization step by the end-user.
*   Requires registering Authorization resources within Gemini Enterprise for each required OAuth client.

**Decision:** Accepted. The operational overhead of storing tokens is natively handled by Gemini Enterprise and ADK, making it an excellent trade-off for increased security, strict enforcement of the user-isolation requirement, and the ability to keep the MCP Servers perfectly stateless.

## 5. Consequences

### 5.1 Positive
*   Faster onboarding of new agents and MCP integration due to decentralized authorization.
*   Maintains the strict principle of least privilege required by ADR-001.
*   Provides a highly transparent consent model for the end-users.

### 5.2 Negative
*   Engineering must register OAuth client configurations (Client ID, Secret, Scopes) as Authorization resources within Gemini Enterprise for production deployments.
*   For CLI-only or headless local execution (without the ADK UI), developers must manually simulate the UX flow or copy-paste authorization codes to cache the initial tokens.

## 6. Implementation Guidelines

*   **Stateless MCP Validation**: MCP Servers must NOT implement `/auth` endpoints or maintain local databases of user tokens. They strictly validate the `Authorization: Bearer <token>` header supplied by the ADK Client on each request cycle.
*   **Gemini Enterprise Authorization Resource**: Administrators must set up Gemini Enterprise with the correct OAuth app credentials, ensuring the redirect URI points to the managed `vertexaisearch` endpoint.
*   **GE-Optimized Header Injection**: For Gemini Enterprise deployments, the agent should proactively retrieve the token from the session context (keyed by `AUTH_ID`) and manually inject it into the `Authorization` header. This avoids redundant interactive challenges and ensures the framework does not attempt a secondary, failing handshake.
*   **Consent Scopes**: Applications should request only the minimum necessary Google API scopes.
*   **Revocation**: The ADK Client system must gracefully handle scenarios where users have manually revoked access via their Google Account, allowing the UI to prompt a re-authorization flow seamlessly.

## 7. References
*   [ADK Documentation: Authenticating with Tools](https://google.github.io/adk-docs/tools-custom/authentication/#2-handling-the-interactive-oauthoidc-flow-client-side)
*   [Gemini Enterprise Documentation: Register and manage ADK agents (Authorization Resources)](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)
