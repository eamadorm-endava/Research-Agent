# Support Case: Gemini Enterprise OAuth Credential Request Not Resuming Tool Execution

## Case summary
Gemini Enterprise (GE) sends requests to a Vertex AI Reasoning Engine backed by ADK `McpToolset` with Drive OAuth configured. The backend repeatedly emits `adk_request_credential` for the configured authorization key, but GE returns `StreamAssist` with `SUCCEEDED` and no useful user response, and execution never reaches the Drive MCP server.

## Impact
- End users cannot complete Drive tasks in GE.
- Agent appears to "answer" with empty/blank response states.
- OAuth prompt behavior is inconsistent or not surfaced.
- No downstream Drive MCP invocation occurs for affected turns.

## Environment
- Project: `p-dev-gce-60pf` (number `753988132239`)
- Region: `us-central1`
- Reasoning Engine: `projects/753988132239/locations/us-central1/reasoningEngines/1867164807765950464`
- GE engine: `projects/753988132239/locations/global/collections/default_collection/engines/gemini-enterprise-app_1774066208827`
- GE agent: `projects/753988132239/locations/global/collections/default_collection/engines/gemini-enterprise-app_1774066208827/assistants/default_assistant/agents/2349478101720749120`
- GE authorization currently attached: `projects/753988132239/locations/global/authorizations/google-drive-authorization-api-3462465657`
- ADK version: `google-adk==1.26.0`

## Current deployed OAuth runtime config
- `DRIVE_OAUTH_CREDENTIAL_KEY=google-drive-authorization-api-3462465657`
- `DRIVE_OAUTH_CLIENT_ID=753988132239-lbguilvja5jol8ups8bv75fl2lsgp3ul.apps.googleusercontent.com`
- `DRIVE_OAUTH_AUTH_URI=https://accounts.google.com/o/oauth2/v2/auth`
- `DRIVE_OAUTH_TOKEN_URI=https://oauth2.googleapis.com/token`
- `DRIVE_OAUTH_REDIRECT_URI=https://vertexaisearch.cloud.google.com/static/oauth/oauth.html`
- Scopes: Drive readonly, drive.file, documents

## Reproduction
1. Open GE and start a fresh session with the agent above.
2. Ask either:
   - "Hi, can you please list my latest files in Drive?"
   - "What tools do you have?"
3. Observe GE behavior (often blank/no actionable response).
4. Check logs as below.

## Observed evidence

### GE StreamAssist logs show SUCCEEDED
Session `5327660192082445818`:
- `2026-03-21T09:20:33.751549327Z` query: "Hi, can you please list my latest files in Drive?" state: `SUCCEEDED`
- `2026-03-21T09:20:56.275969868Z` query: "what tools do you have?" state: `SUCCEEDED`

Session `6291361501267263468`:
- `2026-03-21T09:15:58.556323289Z` query: "Hi, what tools do you have?" state: `SUCCEEDED`
- `2026-03-21T09:16:22.721874527Z` query: "are you authorized? why are you not responding?" state: `SUCCEEDED`

Session `1567114278501981971`:
- Multiple `SUCCEEDED` StreamAssist entries for "Hi, what tools do you have?" and follow-up

### Reasoning Engine receives request and requests credentials
For all affected sessions, logs show:
- `POST /api/stream_reasoning_engine HTTP/1.1" 200 OK`
- then `name: adk_request_credential`
- then explicit key alignment:
  - `credentialKey: google-drive-authorization-api-3462465657`

Examples:
- `2026-03-21T09:20:33.293022Z` name: `adk_request_credential`
- `2026-03-21T09:20:33.293128Z` `credentialKey: google-drive-authorization-api-3462465657`
- `2026-03-21T09:20:55.604518Z` name: `adk_request_credential`
- `2026-03-21T09:20:55.604596Z` `credentialKey: google-drive-authorization-api-3462465657`

### No Drive MCP invocation in affected windows
Drive MCP Cloud Run logs in exact session windows show no requests from this flow (no `/mcp` POST associated with these session timestamps), indicating execution does not proceed from GE credential request phase into tool call phase.

## What has already been tried
1. Rebound GE agent authorization multiple times (detach/attach via API).
2. Recreated GE agent and reattached authorization.
3. Added explicit ADK credential key wiring in runtime:
   - `DRIVE_OAUTH_CREDENTIAL_KEY` in config and deployment env.
4. Verified GE authorization attachment matches runtime credential key.
5. Added debug instrumentation to ADK app for invocation tracing with secret redaction.
6. Confirmed backend emits `adk_request_credential` with correct key post-change.

## Expected vs actual
- Expected:
  - If user already authorized, flow should resume and call Drive MCP tools.
  - If not authorized, GE should clearly surface authorization UI and then resume.
- Actual:
  - GE returns `SUCCEEDED` but user-facing response is blank/insufficient.
  - Backend repeatedly requests credential but no tool execution follows.

## Suspected failure boundary
Gemini Enterprise credential handoff/resume path appears to stop between:
1. receiving `adk_request_credential` from Reasoning Engine
2. providing/restoring credential for the same key
3. resuming turn execution into MCP tool invocation

## Request to support
Please investigate GE handling of ADK `adk_request_credential` for MCP toolsets in this configuration, specifically:
- credential prompt surfacing when request occurs early in turn
- reuse of previously authorized credentials for matching `credentialKey`
- resume semantics after `adk_request_credential`
- reason for `StreamAssist` `SUCCEEDED` responses without progressing to tool execution

## Additional note
Tracking number seen in UI error path: `c2461703136929046` (from GE authorization create attempt conflict).