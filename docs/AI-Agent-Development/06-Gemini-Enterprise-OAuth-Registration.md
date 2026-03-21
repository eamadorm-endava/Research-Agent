# Gemini Enterprise OAuth Registration for Drive MCP

This guide documents the exact process required to register the Research Agent in Gemini Enterprise with Google Drive OAuth enabled, so Drive access is always constrained to the files each end user can actually access.

It complements the general connection notes in `05-Gemini-Enterprise-Connection.md` and captures the extra steps and troubleshooting that were needed for this repository's Drive MCP integration.

## What changed in the codebase

The agent now enables the Google Drive MCP toolset through ADK `McpToolset` with an OAuth 2.0 authorization-code configuration.

That means:

- Gemini Enterprise can detect that the Drive MCP tool requires OAuth.
- Gemini Enterprise can pause execution and request end-user consent.
- After consent, ADK automatically sends `Authorization: Bearer <user-access-token>` to the Drive MCP server.
- The Drive MCP server validates the token and calls Google Drive using the user's delegated permissions.

The service-to-service Cloud Run call remains separate and still uses `X-Serverless-Authorization` when needed.

## Prerequisites

- The agent is already deployed to Vertex AI Agent Engine.
- The Google Drive MCP server is deployed and reachable from the agent.
- The Google Drive MCP server accepts user bearer tokens on the `Authorization` header.
- You have a Gemini Enterprise app already created.
- You have the `Discovery Engine Admin` role.
- You know the Vertex AI Agent Engine reasoning engine resource path.

## Step 1: Create or verify the OAuth client

In the Google Cloud project that owns the Google Drive data access:

1. Open APIs & Services > Credentials.
2. Create or reuse an OAuth Client ID of type `Web application`.
3. Add both Gemini Enterprise redirect URIs:

```text
https://vertexaisearch.cloud.google.com/oauth-redirect
https://vertexaisearch.cloud.google.com/static/oauth/oauth.html
```

4. Save the client.
5. Download the client JSON and keep these values:

- `client_id`
- `client_secret`
- `auth_uri`
- `token_uri`

## Step 2: Configure the agent environment

The agent must be deployed with the Drive MCP OAuth settings present in its environment.

Required values:

```text
DRIVE_URL=https://<drive-mcp-service-base-url>
DRIVE_ENDPOINT=/mcp
DRIVE_OAUTH_CLIENT_ID=<oauth-client-id>
DRIVE_OAUTH_CLIENT_SECRET=<oauth-client-secret>
DRIVE_OAUTH_AUTH_URI=https://accounts.google.com/o/oauth2/v2/auth
DRIVE_OAUTH_TOKEN_URI=https://oauth2.googleapis.com/token
DRIVE_OAUTH_REDIRECT_URI=https://vertexaisearch.cloud.google.com/static/oauth/oauth.html
```

How to populate each value:

- `DRIVE_URL`: Cloud Run base URL of your deployed Drive MCP service (without `/mcp`).
  - Example: `https://drive-mcp-server-<hash>-uc.a.run.app`
  - Source: Cloud Run > Services > your Drive MCP service > Service URL
- `DRIVE_ENDPOINT`: Keep `/mcp` unless your Drive MCP server was deployed with a custom MCP path.
- `DRIVE_OAUTH_CLIENT_ID`: OAuth Client ID from APIs & Services > Credentials.
- `DRIVE_OAUTH_CLIENT_SECRET`: OAuth Client Secret from APIs & Services > Credentials.
- `DRIVE_OAUTH_AUTH_URI`: Keep `https://accounts.google.com/o/oauth2/v2/auth`.
- `DRIVE_OAUTH_TOKEN_URI`: Keep `https://oauth2.googleapis.com/token`.
- `DRIVE_OAUTH_REDIRECT_URI`: Use `https://vertexaisearch.cloud.google.com/static/oauth/oauth.html` for Gemini Enterprise.

Optional but recommended related values for this project:

```text
PROJECT_ID=<your-gcp-project-id>
REGION=<your-agent-engine-region>
BIGQUERY_URL=<your-bigquery-mcp-cloud-run-url>
BIGQUERY_ENDPOINT=/mcp
GCS_URL=<your-gcs-mcp-cloud-run-url>
GCS_ENDPOINT=/mcp
GENERAL_TIMEOUT=60
```

If you are redeploying through `agent/deployment/deploy.py`, pass them in `--set-env-vars` as a single comma-separated string. Example template:

```bash
uv run --group ai-agent --group dev python -m agent.deployment.deploy \
  --project <PROJECT_ID> \
  --location <REGION> \
  --display-name "<AGENT_DISPLAY_NAME>" \
  --source-packages=./agent \
  --entrypoint-module=agent.core_agent.agent \
  --entrypoint-object=app \
  --requirements-file=./agent/core_agent/requirements.txt \
  --service-account=<AGENT_SERVICE_ACCOUNT>@<PROJECT_ID>.iam.gserviceaccount.com \
  --set-env-vars="PROJECT_ID=<PROJECT_ID>,REGION=<REGION>,DRIVE_URL=https://drive-mcp-server-<hash>-uc.a.run.app,DRIVE_ENDPOINT=/mcp,DRIVE_OAUTH_CLIENT_ID=<OAUTH_CLIENT_ID>,DRIVE_OAUTH_CLIENT_SECRET=<OAUTH_CLIENT_SECRET>,DRIVE_OAUTH_AUTH_URI=https://accounts.google.com/o/oauth2/v2/auth,DRIVE_OAUTH_TOKEN_URI=https://oauth2.googleapis.com/token,DRIVE_OAUTH_REDIRECT_URI=https://vertexaisearch.cloud.google.com/static/oauth/oauth.html,DRIVE_OAUTH_SCOPES=[\"https://www.googleapis.com/auth/drive.readonly\",\"https://www.googleapis.com/auth/drive.file\",\"https://www.googleapis.com/auth/documents\"],BIGQUERY_URL=<BIGQUERY_MCP_URL>,BIGQUERY_ENDPOINT=/mcp,GCS_URL=<GCS_MCP_URL>,GCS_ENDPOINT=/mcp,GENERAL_TIMEOUT=60"
```

Recommended scopes for this repository (configured on the agent side through `DRIVE_OAUTH_SCOPES`):

```text
https://www.googleapis.com/auth/drive.readonly
https://www.googleapis.com/auth/drive.file
https://www.googleapis.com/auth/documents
```

Notes:

- `DRIVE_OAUTH_REDIRECT_URI` should match the Gemini Enterprise redirect flow, not the local ADK UI callback, for production deployments.
- If `DRIVE_OAUTH_CLIENT_ID` or `DRIVE_OAUTH_CLIENT_SECRET` is missing, the agent now skips registering the Drive MCP toolset at startup. That prevents a broken deployment where the tool exists but cannot trigger OAuth.

## Step 3: Re-deploy the agent

Re-deploy the Vertex AI Agent Engine app after updating the environment variables.

Before re-deploying, verify these minimum values are not empty:

- `DRIVE_URL`
- `DRIVE_OAUTH_CLIENT_ID`
- `DRIVE_OAUTH_CLIENT_SECRET`
- `DRIVE_OAUTH_REDIRECT_URI`

The important validation point is that the deployed agent must expose the Drive MCP tool as an OAuth-enabled `McpToolset`. Without that, Gemini Enterprise will never show the consent flow.

## Step 4: Create the Gemini Enterprise authorization resource

Create an authorization resource in Gemini Enterprise for the same OAuth client.

In the Google Cloud console:

1. Open Gemini Enterprise.
2. Open the app where the Research Agent will be available.
3. Go to Agents.
4. Click Add agent.
5. Choose Custom agent via Agent Engine.
6. In the Authorizations step, click Add authorization.
7. Enter an authorization name.
8. Fill in the authorization settings using the OAuth client created earlier:

- Client ID: the OAuth client ID from APIs & Services > Credentials
- Client secret: the OAuth client secret from APIs & Services > Credentials
- Authorization URI: use a full Google authorization URL, not just the base auth endpoint
- Token URI: `https://oauth2.googleapis.com/token`

9. Save the authorization.

For Google authorization servers, the Authorization URI must include the query parameters required by Gemini Enterprise. Use this template and replace `YOUR_CLIENT_ID` with your OAuth client ID:

```text
https://accounts.google.com/o/oauth2/v2/auth?client_id=YOUR_CLIENT_ID&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Fstatic%2Foauth%2Foauth.html&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive.readonly%20https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive.file%20https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdocuments&include_granted_scopes=true&response_type=code&access_type=offline&prompt=consent
```

Important details:

- The OAuth client itself must already include both Gemini Enterprise redirect URIs in APIs & Services > Credentials.
- The scopes encoded in the Authorization URI must cover every Drive operation your agent exposes:
  - `https://www.googleapis.com/auth/drive.readonly`
  - `https://www.googleapis.com/auth/drive.file`
  - `https://www.googleapis.com/auth/documents`
- `access_type=offline` is required for Google authorization servers, otherwise Gemini Enterprise rejects the authorization resource.
- `prompt=consent` is recommended so the consent flow reliably returns the refresh-token-capable response Gemini Enterprise expects.
- In this console-based registration flow, Gemini Enterprise uses the OAuth client, authorization URI, and token endpoint from the authorization resource. The agent-side ADK configuration should request the same scopes through `DRIVE_OAUTH_SCOPES` so both sides stay aligned.
- Gemini Enterprise manages the consent redirect and token lifecycle after this authorization is attached to the agent.

## Step 5: Delete and re-register the agent in Gemini Enterprise

This repository's spec requires deleting the prior Gemini Enterprise registration and creating it again with OAuth permissions.

Recommended sequence:

1. Open Gemini Enterprise in the Google Cloud console.
2. Open the target app.
3. Go to Agents.
4. Locate the old Research Agent registration.
5. Open the agent details and delete that registration.
6. Click Add agent.
7. Choose Custom agent via Agent Engine.
8. In the Authorizations step, select the authorization resource created in Step 4.
9. Continue to the agent configuration step.
10. Enter the display name and description.
11. Paste the Agent Engine reasoning engine resource path.
12. Create the agent.

When registering again, use the Agent Engine reasoning engine path in this format:

```text
https://<LOCATION>-aiplatform.googleapis.com/v1/projects/<PROJECT_ID>/locations/<LOCATION>/reasoningEngines/<RESOURCE_ID>
```

Recommended checks before clicking Create:

- The reasoning engine path points to the latest deployed agent version.
- The selected authorization is the one backed by the correct OAuth client.
- The app and reasoning engine locations are compatible.

## Step 6: Validate the OAuth flow in Gemini Enterprise

Use a Drive-specific prompt after registration, for example:

- "List the latest files in my Google Drive"
- "Open the text of my Q1 planning doc"
- "Create a Google Doc in my Drive named Weekly Summary"

Expected behavior:

1. Gemini Enterprise prompts the user to authenticate.
2. The user sees the Google consent screen.
3. After consent, the same prompt succeeds without asking again immediately.
4. Results are restricted to the user's own Drive permissions.

Expected technical behavior:

- The agent sends the request to Drive MCP using `Authorization: Bearer <user-access-token>`.
- If the Drive MCP service is protected by Cloud Run IAM, the request also includes `X-Serverless-Authorization: Bearer <id-token>`.
- The Drive MCP server validates the user token and uses it to call Drive APIs.

## Troubleshooting

### Symptom: No consent prompt appears in Gemini Enterprise

Likely causes:

- The deployed agent did not include the Drive MCP toolset.
- `DRIVE_OAUTH_CLIENT_ID` or `DRIVE_OAUTH_CLIENT_SECRET` was missing at deployment time.
- The Gemini Enterprise registration points to an outdated Agent Engine deployment.

Checks:

- Re-deploy the agent with the Drive OAuth env vars set.
- Re-register the agent after deployment.
- Confirm the reasoning engine path is the current one.
- Confirm the test prompt is explicitly Drive-related (for example: `Use your Google Drive tools to list my 5 most recent files`).

### Symptom: Consent appears, then the conversation returns no output

Likely cause:

- The run emitted `adk_request_credential` but Gemini Enterprise did not complete the credential callback event, so execution stopped waiting for credentials.

Checks:

- Use a URL-encoded Authorization URI in Gemini Enterprise (encode scopes and redirect URI; do not leave raw spaces in `scope`).
- Delete and recreate the Gemini Enterprise authorization resource after correcting the URI.
- Re-attach that authorization to the agent registration.
- Start a new chat/session in Gemini Enterprise and retry with an explicit Drive tool prompt.

### Symptom: Consent prompt appears, but Drive tool still fails with unauthenticated errors

Likely causes:

- Missing Drive scopes in the OAuth client or authorization resource.
- Redirect URI mismatch.
- Token audience or token exchange mismatch caused by a stale authorization resource.

Checks:

- Verify the registered authorization resource uses the correct client ID and token URI.
- Verify the Authorization URI includes `access_type=offline`, `response_type=code`, and the Gemini Enterprise redirect URI.
- Verify the OAuth client in APIs & Services includes the Gemini Enterprise redirect URIs.
- Delete and recreate the authorization in the console if configuration drift is suspected.

### Symptom: Gemini Enterprise says the authorization URI must contain `access_type=offline`

Likely cause:

- The authorization resource was created with the base Google auth endpoint instead of the full authorization URI Gemini Enterprise expects.

Fix:

- Edit or recreate the authorization resource.
- Set the Authorization URI to the full Google OAuth URL including:
  - `client_id=<your-client-id>`
  - `redirect_uri=https://vertexaisearch.cloud.google.com/static/oauth/oauth.html`
  - `scope=<url-encoded scopes>`
  - `include_granted_scopes=true`
  - `response_type=code`
  - `access_type=offline`
  - `prompt=consent`

### Symptom: Cloud Run returns `403` before the Drive MCP server processes the request

Likely cause:

- The agent service account lacks permission to invoke the Drive MCP Cloud Run service.

Checks:

- Confirm the agent includes `X-Serverless-Authorization` for the Drive MCP base URL.
- Grant the agent service account `roles/run.invoker` on the Drive MCP service.

### Symptom: Gemini Enterprise returns a reasoning engine permission error

Typical error:

```json
{
  "error": {
    "code": 500,
    "message": "Reasoning Engine Execution Service stream failed with status code PERMISSION_DENIED"
  }
}
```

Fix:

- Grant the Discovery Engine service agent the required Vertex AI access described in `05-Gemini-Enterprise-Connection.md`.

### Symptom: Users can authenticate, but they cannot see expected shared Drive files

Likely cause:

- This is now a real Drive permission issue instead of a service-account overreach issue.

Checks:

- Verify the target file is actually shared with the signed-in user.
- Verify the file exists in a shared drive or location the user can access.
- Test with another user to confirm behavior follows the user identity, not the backend service identity.

## Completion checklist

- Agent deployed with Drive OAuth environment variables.
- Gemini Enterprise authorization resource created.
- Previous Gemini Enterprise agent registration deleted.
- Agent registered again with the correct authorization attached.
- OAuth prompt tested successfully in Gemini Enterprise.
- Drive reads and writes verified against user-scoped permissions.