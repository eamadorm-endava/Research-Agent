# Atlassian OAuth 2.0 / 3LO Setup for Jira and Confluence MCP

To allow the AI Agent and the Atlassian MCP Server to read Jira and Confluence data on behalf of the current user, you must register an OAuth 2.0 / 3LO application in Atlassian.

> [!NOTE]
> **Atlassian authentication must use its own OAuth application.** Microsoft Entra SSO can still be the visible login experience if the Atlassian organization is configured to authenticate through Microsoft, but the token sent to the MCP server must be an Atlassian access token. Do not reuse the Microsoft Entra OAuth app, client ID, client secret, or Auth ID for Jira and Confluence.

Follow these steps to configure the Atlassian app, enable the required read-only scopes, create the Gemini Enterprise Auth ID, and deploy the agent and MCP server with delegated user authentication.

## 1. Create the Atlassian OAuth Application

1. Go to the [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/) and log in with an Atlassian administrator or app owner account.
2. Click **Create** > **OAuth 2.0 integration**.
3. **Name**: Provide a descriptive name for the integration (e.g., `OSIRIS Gemini Enterprise Atlassian MCP`).
4. Click **Create**.

## 2. Enable OAuth 2.0 / 3LO

1. In the Atlassian app, open **Authorization** from the left menu.
2. Next to **OAuth 2.0 (3LO)**, click **Configure**.
3. Add the callback URL required by the environment:
   - `http://localhost:8000/dev-ui/` -> For local testing with ADK Web.
   - `https://vertexaisearch.cloud.google.com/static/oauth/oauth.html` -> For Gemini Enterprise.
4. Save the authorization configuration.

> [!IMPORTANT]
> The callback URL must exactly match the redirect URI used by the agent runtime. If you are testing from Cloud Shell and ADK Web redirects through a forwarded Cloud Shell URL, add that forwarded `/dev-ui/` URL to the Atlassian app or use a separate Atlassian app/environment for local testing.

## 3. Define API Permissions (Scopes)

1. In the Atlassian app, open **Permissions**.
2. Add **Jira API** and configure the following delegated read scopes:
   - `read:jira-work`: Required to list Jira projects, read project metadata, search issues, and read issue fields.
   - `read:jira-user`: Required to read Jira user profile information that appears in project or issue responses.
3. Add **Confluence API** and configure the following delegated read scopes:
   - `read:space:confluence`: Required to list and read Confluence spaces.
   - `read:page:confluence`: Required to list, search, and read Confluence pages.
   - `read:attachment:confluence`: Required to list and read Confluence page attachments metadata.
   - `read:comment:confluence`: Required to list Confluence page comments.
   - `read:label:confluence`: Required to list Confluence labels.
   - `search:confluence`: Required for Confluence search operations.
4. The agent also requests `offline_access` so Atlassian can issue refresh-capable tokens.

> [!NOTE]
> This MCP server is read-only. Do not add or request `write:confluence-content` unless the MCP tool surface is intentionally changed to expose write operations.

## 4. Copy the Atlassian OAuth Credentials

1. In the Atlassian app, open **Settings**.
2. Copy the **Client ID**. This is your `ATLASSIAN_OAUTH_CLIENT_ID`.
3. Copy the **Secret**. This is your `ATLASSIAN_OAUTH_CLIENT_SECRET`.

> [!IMPORTANT]
> Treat the Atlassian client secret as a production secret. Do not commit it to the repository or store it in plaintext configuration files outside local development.

## 5. Store Credentials in GCP Secret Manager

The AI Agent Cloud Build pipeline reads the Atlassian OAuth credentials from Secret Manager when creating or updating the Gemini Enterprise Auth ID.

Create the secrets if they do not exist:

```bash
printf "%s" "<atlassian-client-id>" | gcloud secrets create ATLASSIAN_OAUTH_CLIENT_ID \
  --data-file=- \
  --project <PROJECT_ID>

printf "%s" "<atlassian-client-secret>" | gcloud secrets create ATLASSIAN_OAUTH_CLIENT_SECRET \
  --data-file=- \
  --project <PROJECT_ID>
```

If the secrets already exist, add new versions instead:

```bash
printf "%s" "<atlassian-client-id>" | gcloud secrets versions add ATLASSIAN_OAUTH_CLIENT_ID \
  --data-file=- \
  --project <PROJECT_ID>

printf "%s" "<atlassian-client-secret>" | gcloud secrets versions add ATLASSIAN_OAUTH_CLIENT_SECRET \
  --data-file=- \
  --project <PROJECT_ID>
```

## 6. Configure the Gemini Enterprise Auth ID

The repository Cloud Build configuration creates an Atlassian Gemini Enterprise Auth ID using:

```bash
GEMINI_ATLASSIAN_AUTH_ID=atlassian-authentication
```

For CI/test environments, the default Auth ID may be:

```bash
GEMINI_ATLASSIAN_AUTH_ID=atlassian-authentication-test-v2
```

The Auth ID must be created with:

```text
Authorization endpoint: https://auth.atlassian.com/authorize
Token endpoint:         https://auth.atlassian.com/oauth/token
Authorization extras:   audience=api.atlassian.com
Prompt:                 consent
Token auth method:      client_secret_post
```

The scopes used by the current read-only Atlassian MCP are:

```text
offline_access read:jira-work read:jira-user read:space:confluence read:page:confluence read:attachment:confluence read:comment:confluence read:label:confluence search:confluence
```

> [!NOTE]
> The deployed agent retrieves the user's delegated Atlassian token from Gemini Enterprise using `GEMINI_ATLASSIAN_AUTH_ID` and forwards it to the Atlassian MCP through the `Authorization` header. The MCP then validates the token through Atlassian's `accessible-resources` endpoint and calls Jira/Confluence through the `api.atlassian.com/ex/.../{cloudId}` gateway.

## 7. Configure Local Testing

For local ADK Web testing, the agent needs the Atlassian OAuth client configuration in the `.env` file loaded by the agent. In this repository, local ADK logs should confirm which file is loaded, commonly:

```text
agent/core_agent/.env
```

Add or verify the following values:

```bash
PROD_EXECUTION=False

ATLASSIAN_URL=http://localhost:8085

ATLASSIAN_OAUTH_CLIENT_ID=<your-atlassian-3lo-client-id>
ATLASSIAN_OAUTH_CLIENT_SECRET=<your-atlassian-3lo-client-secret>
ATLASSIAN_OAUTH_REDIRECT_URI=http://localhost:8000/dev-ui/
ATLASSIAN_OAUTH_AUTH_URI=https://auth.atlassian.com/authorize?audience=api.atlassian.com&prompt=consent
ATLASSIAN_OAUTH_TOKEN_URI=https://auth.atlassian.com/oauth/token
ATLASSIAN_OAUTH_TOKEN_ENDPOINT_AUTH_METHOD=client_secret_post
ATLASSIAN_OAUTH_SCOPES='["offline_access","read:jira-work","read:jira-user","read:space:confluence","read:page:confluence","read:attachment:confluence","read:comment:confluence","read:label:confluence","search:confluence"]'
```

The Atlassian MCP server itself is OAuth-only. It does not need static Atlassian user credentials. It can optionally use `JIRA_CLOUD_ID` when the user has access to multiple Atlassian sites and a specific site must be selected:

```bash
JIRA_CLOUD_ID=<atlassian-cloud-id>
```

## 8. Run the Local OAuth Flow

Start the local Atlassian MCP server:

```bash
make run-atlassian-mcp-locally
```

Start the ADK Web agent in another terminal:

```bash
make run-ui-agent
```

Open ADK Web and trigger an Atlassian read operation:

```text
Use Atlassian to list the Jira projects I can access.
```

or:

```text
Use Atlassian to list the Confluence spaces I can access.
```

Expected flow:

```text
ADK Web agent
→ Atlassian OAuth authorization page
→ Microsoft SSO login if Atlassian is configured with Microsoft SSO
→ Atlassian consent screen
→ ADK receives an Atlassian access token
→ Agent forwards the token to the local Atlassian MCP
→ MCP calls Jira/Confluence as the current user
```

## 9. Deploy the MCP Server and Agent

For deployment, use this order:

1. Deploy the Atlassian MCP Cloud Run service.
2. Deploy the AI Agent and create/update the Gemini Enterprise Auth IDs.
3. Register the agent in Gemini Enterprise.
4. Have the user authorize the Atlassian app from Gemini Enterprise when the first Jira or Confluence tool is called.

The deployed agent must receive:

```bash
ATLASSIAN_URL=https://atlassian-mcp-server-<PROJECT_NUMBER>.<REGION>.run.app
GEMINI_ATLASSIAN_AUTH_ID=<deployed-atlassian-auth-id>
```

The Atlassian MCP Cloud Run service must be protected by Cloud Run IAM and invokable by the agent service account. The request has two auth layers:

1. `X-Serverless-Authorization`: Cloud Run service-to-service ID token from the agent.
2. `Authorization`: Delegated Atlassian access token for the current user.

## 10. General Troubleshooting

### The popup says scopes have not been added to the app

Add the exact requested scopes to the Atlassian Developer Console. Scopes approved by the user are not enough; the scopes must also be configured on the Atlassian OAuth app.

### Confluence returns `401 Unauthorized; scope does not match`

The MCP uses Confluence REST API v2 endpoints. Confirm the Auth ID and Atlassian app use granular Confluence scopes such as `read:space:confluence` and `read:page:confluence`, not only classic scopes like `read:confluence-content.all` or `read:confluence-space.summary`.

### Jira or Confluence returns data from the wrong Atlassian site

Set `JIRA_CLOUD_ID` on the Atlassian MCP deployment to force the Cloud ID returned by Atlassian's `accessible-resources` endpoint.

### Gemini Enterprise says an OAuth token was found, but the tool still fails

Check the Atlassian MCP Cloud Run logs. If the MCP endpoint returns HTTP 200 but the tool result contains an error, the network call succeeded and the failure is inside the Atlassian API call, usually scopes, Cloud ID selection, or stale deployed code.

### Updated scopes are not taking effect

Force a fresh user authorization. In test environments, the fastest option is often to create a new Auth ID, for example `atlassian-authentication-test-v3`, update `GEMINI_ATLASSIAN_AUTH_ID`, and redeploy/register the agent.

## 12. Reference Documentation

- [Atlassian OAuth 2.0 / 3LO apps](https://developer.atlassian.com/cloud/confluence/oauth-2-3lo-apps/)
- [Implementing OAuth 2.0 / 3LO authorization code flow](https://developer.atlassian.com/cloud/oauth/getting-started/implementing-oauth-3lo/)
- [Making calls to Atlassian APIs with 3LO tokens](https://developer.atlassian.com/cloud/oauth/getting-started/making-calls-to-api/)
- [Jira OAuth 2.0 scopes](https://developer.atlassian.com/cloud/jira/platform/scopes-for-oauth-2-3LO-and-forge-apps/)
- [Confluence REST API v2 space scopes](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-space/)
