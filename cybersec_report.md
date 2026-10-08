# Vulnerability Report

Scope reduced at the user's request: deployment/runtime fixes and the IAP/OAuth
checks necessary for the existing UI. General optimization and new features are
excluded. The existing proxy-only subnet was imported into the GCS-backed
Terraform state as explicitly requested; no Terraform apply was executed.

| Risk Level | File(s) | Rationale | Possible Fix |
| :--- | :--- | :--- | :--- |
| **Urgent** | — | No open urgent finding in the retained changes. | — |
| **High** | `ui/backend/auth.py`, `ui/backend/routers/oauth.py`, `ui/backend/oauth_state.py` | The previous unsigned-identity/mock-user and unvalidated OAuth-state findings remain fixed. Production verifies signed IAP assertions. OAuth state is short-lived, browser/user/provider-bound and consumed once. | Retain the focused authentication tests. |
| **Medium** | Existing UI/agent IAM and token storage | Existing project-level roles and shared token storage are retained. Broad privilege/isolation changes are outside this minimal patch. | Review resource/database-scoped access in a separate hardening change. |
| **Medium** | `ui/backend/limits.py` | SlowAPI enforces configurable per-instance limits. Multiple instances increase the aggregate quota. | Use a shared quota backend when aggregate quotas are needed. |
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


## Follow-up practice review

All `.agents/rules/*.md` and skill instructions were reviewed against this fix.
Applicable code checks now include Pydantic Annotated fields, provider validation
and callback-path construction in a request model, named dictionary returns,
explicit CORS, HSTS/CSP/nosniff and SlowAPI request limits. OAuth popup behavior
is retained with an exact CSP script hash; cookies remain HttpOnly/Secure/Lax.
Python execution uses uv with feature dependency groups. Lint, tests, validation
and state import commands are available in the single root Makefile.

The app group is `osiris_app_users@endava.com`. Trigger filters contain neither
tests nor `pyproject.toml`/`uv.lock`. Shared apply runs the binary copied from
Terraform's official 1.12.2 init image inside Cloud SDK, with one args list.
The successful CLI import targeted the existing GCS backend and left the subnet
resource declared without import blocks. No new upload feature, refresh-lock
framework, state-backend migration or deployment orchestrator was introduced.

Existing state naming/layout and inherited raw resources are retained to honor
the user's minimal-change and existing-environment instructions. New-feature
issue/notebook lifecycle, production acceptance and PR merge are release/process
steps; they were not fabricated as completed by this code review. GitHub CodeQL
alert status could not be queried with the currently unauthenticated GitHub CLI.

The final checks include 27 UI tests (including CORS, header and rate-limit
regressions), full lint/format checks for the backend and tests, Terraform
validation for four stacks and a successful backend image build. The copied
Terraform executable was verified as 1.12.2 in Cloud SDK alongside bq and Bash.
