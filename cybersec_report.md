# Vulnerability Report

Scope: shared resources, gateway dependency/state handling, `terraform/ui*_resources`,
`ui/`, shared OAuth token storage and their deployment pipelines. Remediation branch:
`fix/ui-shared-resources`, based on `origin/main` (`b88f59b`). Review date: 2026-10-08.

Open findings: **0 Urgent, 0 High, 2 Medium**.

| Risk Level | File(s) | Rationale | Possible Fix |
| :--- | :--- | :--- | :--- |
| **Urgent** | — | No open urgent finding in the reviewed changes. | — |
| **High** | `ui/backend/auth.py`, `ui/backend/routers/oauth.py`, `ui/backend/oauth_state.py` | Previous high findings are closed: unsigned identity headers/mock users are rejected in production; OAuth state is bound to the verified user, provider and secure browser cookie, expires and is consumed transactionally. IAP verifies ES256 signatures, issuer, trusted audiences and token lifetime. | Maintain regression coverage for forged identities, replay, provider/user mismatch and missing configuration. |
| **Medium** | `ui/backend/limits.py` | Application request limits are per instance. Multiple instances increase the effective aggregate limit; limits also reset on restart. IAP restricts entry to configured users/groups. | Add a shared quota service or Cloud Armor when aggregate quotas are needed. |
| **Medium** | `agent/core_agent/security/token_store.py`, UI/agent Firestore IAM | Backend and agent service accounts use project-level `roles/datastore.user`; a compromised service account can access other database documents permitted by that role. Production and test use separate collections but the shared service accounts are trusted for both. | For stronger environment isolation, split databases/projects and runtime service accounts and scope IAM at database level. |
| **Low** | `ui/backend/routers/oauth.py` | Google/Microsoft use S256 PKCE. Atlassian uses its documented confidential Jira/Confluence 3LO exchange, whose documented contract does not specify the same PKCE parameters. | Follow the provider's documented flow; retain validated state/browser binding and client-secret protection. |

## Closed findings and operational corrections

- Removed `local-exec` dependency on missing `bq`/Bash from Terraform. Cloud SDK
  runs the idempotent model check using its credentials and the BigQuery REST API.
  A read failure is not misclassified as a missing model; creation success is
  independently verified. Removing the null resource does not delete the model.
- All four load-balancer backend services explicitly disable health checks for
  serverless NEGs. The backend creates the IAP service identity before invoker IAM.
  API routes have separate IAP-protected backend services and access bindings.
- Preserved `mcp-agent-vpc` and reserved IP **136.81.113.202**. Frontend egress uses
  the VPC and its app subnet has Private Google Access enabled. Compatibility
  checks and conditional state imports resolve the existing proxy-subnet and
  unmanaged-test-service conflicts without deleting those resources.
- App Secret Accessor is scoped to six secrets; frontend Run Invoker is scoped
  to UI backends. Audience discovery has a custom single-permission role. Upload
  signing is scoped to the backend's own account and bucket access to object creation.
  The deployer receives role/IAP administration for infrastructure management;
  application service accounts do not receive those administrative roles.
- Agent Engine resolves by an exact configured display name rather than a stale
  ID. Authenticated readiness checks a fresh lookup and reports unavailable or
  ambiguous agents. Session ownership is verified before reuse. Stream failure
  is explicit and does not produce a terminal success event.
- Provider calls have timeouts and run in worker threads rather than blocking
  async handlers. A Firestore lease coordinates rotating-token refresh; a
  transactional compare-and-set also prevents overwriting a concurrent reconnect.
  Ephemeral authorization/refresh records have TTL cleanup.
- CORS uses configured origins; private responses prohibit caching and set
  HSTS, CSP and nosniff headers. Token responses, full agent events and file-based
  debug logs are not emitted. User/agent/tool content is rendered without unsafe
  HTML; thought parts are omitted.
- Replaced upload placeholders with signed, bounded, user-isolated PUT uploads.
  Docker images use locked dependency groups, Python slim wheels and a nonroot
  user. Importing shared config/storage does not initialize ADK telemetry or ADC
  clients in the UI process.
- One push pipeline orders UI dependencies. PR pipelines do not apply production
  Terraform state or redeploy shared test services. Trigger reconciliation updates
  existing filters, includes shared code/locks and removes the obsolete independent
  backend push trigger. Test agent/token collection configuration is consistent.

## Evidence and limits

Read-only GCP inspection confirmed the embedding model and Firestore `osiris`,
original network, missing proxy-subnet Terraform state, production/test Cloud Run
services, and reserved IP `136.81.113.202`. The live production Agent Engine is
named `OSIRIS`; there was no live `OSIRIS - Test` at inspection time. Test UI
acceptance therefore requires deploying the agent CI target, which CD now preserves.

Validation includes the UI/infrastructure regression suite, existing agent suite,
Ruff/shell checks, Terraform validation for all four affected stacks, locked builds
of both Docker images, and container startup/liveness probes. Exact final counts
are recorded in the completion message. Tests mock OAuth, ADC, Firestore and
Agent Engine calls; a fresh isolated dependency environment also runs the CI suite.

No Terraform apply, cloud state import, IAM grant, trigger modification, provider
consent or production conversation was executed during this branch preparation.
The prepared deployment performs those infrastructure operations only when invoked.
Live HTTPS/IAP/OAuth/conversation/upload acceptance remains a deployment check.

References: [IAP assertion validation](https://docs.cloud.google.com/iap/docs/signed-headers-howto),
[Cloud Run private networking](https://docs.cloud.google.com/run/docs/securing/private-networking),
[Atlassian confidential 3LO](https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/).
