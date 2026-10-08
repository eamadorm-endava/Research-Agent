# Vulnerability Report

Scope reduced at the user's request: deployment/runtime fixes and the IAP/OAuth
checks necessary for the existing UI. General optimization and new features are
excluded. No infrastructure was applied during branch preparation.

| Risk Level | File(s) | Rationale | Possible Fix |
| :--- | :--- | :--- | :--- |
| **Urgent** | — | No open urgent finding in the retained changes. | — |
| **High** | `ui/backend/auth.py`, `ui/backend/routers/oauth.py`, `ui/backend/oauth_state.py` | The previous unsigned-identity/mock-user and unvalidated OAuth-state findings remain fixed. Production verifies signed IAP assertions. OAuth state is short-lived, browser/user/provider-bound and consumed once. | Retain the focused authentication tests. |
| **Medium** | Existing UI/agent IAM and token storage | Existing project-level roles and shared token storage are retained. Broad privilege/isolation changes are outside this minimal patch. | Review resource/database-scoped access in a separate hardening change. |
| **Medium** | `ui/backend/main.py`, existing UI request handling | Existing CORS and request-limiting behavior are retained. General web hardening is outside this minimal patch. | Review allowed origins and rate limits separately. |
| **Low** | Existing Streamlit rendering | Existing HTML/layout behavior is retained; no new HTML rendering or upload feature is introduced. | Review untrusted-content rendering separately. |

CodeQL alert #10: cookie names and paths are returned as literal constants for
Google, Microsoft and Atlassian. The value remains a server-generated random
secret. Set/read/delete use the same fixed metadata; no rule suppression is used.
The remote alert status requires GitHub's next analysis.

Verification: focused IAP/OAuth regression tests, Python/YAML/shell syntax and
Terraform fmt/validate for shared resources, gateway and both UI stacks. The
shared provisioner now runs in Cloud SDK with Terraform 1.12.2, Bash and `bq`.
The existing UI layout, individual pipelines and agent deployment are retained;
the reserved IP is `136.81.113.202` and the VPC is `mcp-agent-vpc`.
