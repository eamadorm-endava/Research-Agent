# Setup Guide — Method 2: Per-User OAuth 2.0 (Browser Redirect)

**Best for:** Orgs without Workspace Admin access, or mixed personal/Workspace users.  
**User interaction:** Each user authenticates once via Google consent screen.  
**Requires:** OAuth 2.0 Client ID (Web application type) — no admin access needed.

---

## Prerequisites

- A GCP project with billing enabled
- Ability to create OAuth credentials in GCP Console (Project Editor or above)

---

## Step 1 — Enable Required APIs

In [GCP Console](https://console.cloud.google.com) → **APIs & Services** → **Enable APIs and Services**:

- ✅ Target GCP API (e.g., Google Drive API, BigQuery API)

```bash
# Replace <api-name> with drive.googleapis.com, bigquery.googleapis.com, etc.
gcloud services enable <api-name>.googleapis.com
```

---

## Step 2 — Create OAuth 2.0 Credentials

Setting up OAuth involves configuring the **Consent Screen** (the page users see when logging in) and creating a **Client ID** (the unique identity for your Agent application).

### 2a. Initiate Client Creation
1. In the GCP Console, navigate to **APIs & Services** → **Credentials**.
2. Click **Create Credentials** → **OAuth client ID**.
3. Select **Web application** as the application type.
4. If you see the message *"To create an OAuth client ID, you must first configure your consent screen"*:
    - Click **Configure Consent Screen**.
    - Choose **User Type** and carefully consider the implications:
      - **Internal**: Best for tools restricted to your organization's Google Workspace users. This option bypasses Google's rigorous app verification process entirely, allowing immediate use of sensitive scopes (like Drive) without user caps.
      - **External**: Required if users outside your organization (including standard `@gmail.com` users) need access. If requesting sensitive/restricted scopes, your app will be capped at 100 users and show an "unverified app" warning until it passes Google's official security and verification review.
    - Fill in the required fields (**App name**, **User support email**, **Developer contact email**).
    - Click **Save and Continue**.

### 2b. Add Scopes (Data Access)
1. In the **Scopes** (Data Access) section of the Consent Screen configuration, click **Add or remove scopes**.
2. Search for and add the necessary scopes for your target service.

| Service | Required Scope |
| :--- | :--- |
| **Google Drive** | `https://www.googleapis.com/auth/drive` |
| **BigQuery** | `https://www.googleapis.com/auth/bigquery` |
| **Cloud Storage** | `https://www.googleapis.com/auth/cloud-platform` |
| **Google Sheets** | `https://www.googleapis.com/auth/spreadsheets` |

3. Click **Update** → **Save and Continue**.

### 2c. Publish App
1. On the final summary page, click **Back to Dashboard** or go to **OAuth consent screen**.
2. Click **Publish App** and confirm. This prevents refresh tokens from expiring after 7 days.

### 2d. Finalize and Download Client JSON
1. Return to **APIs & Services** → **Credentials**.
2. Click **Create Credentials** → **OAuth client ID** again (if not already completed).
3. **Application type**: `Web application`.
4. **Name**: `Agent OAuth Client`.
5. **Authorized redirect URIs**:
    - For **Gemini Enterprise**: `https://vertexaisearch.cloud.google.com/oauth-redirect` and `https://vertexaisearch.cloud.google.com/static/oauth/oauth.html`
    - For **Local ADK UI Development**: `http://localhost:<PORT>/oauth2callback` (optional, depends on local setup)

6. Click **Create**.
7. In the confirmation dialog, click **Download JSON**. This file contains your `client_id` and `client_secret` needed for the next step.

---

## Step 3 — Register Authorization Resource (Gemini Enterprise)

Because the MCP server is completely stateless regarding authentication, you do **not** configure the Client Secret or Token store on the MCP server itself.

Instead of configuring secrets directly on the MCP server, you must register an **Authorization Resource** in Gemini Enterprise. This tells the platform which OAuth client to use for user sessions.

For the complete 5-step production setup including GE-optimized registration, follow the **[OAuth inside Gemini Enterprise Guide](../AI-Agent-Development/06-OAuth-Inside-Gemini-Enterprise.md)**.

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: YOUR_PROJECT_ID" \
  "https://us-discoveryengine.googleapis.com/v1alpha/projects/YOUR_PROJECT_ID/locations/global/authorizations?authorizationId=MY_AUTH_RESOURCE_ID" \
  -d '{
    "name": "projects/YOUR_PROJECT_ID/locations/global/authorizations/MY_AUTH_RESOURCE_ID",
    "serverSideOauth2": {
      "clientId": "YOUR_CLIENT_ID",
      "clientSecret": "YOUR_CLIENT_SECRET",
      "authorizationUri": "https://accounts.google.com/o/oauth2/v2/auth?client_id=YOUR_CLIENT_ID&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Fstatic%2Foauth%2Foauth.html&scope=YOUR_SCOPES&include_granted_scopes=true&response_type=code&access_type=offline&prompt=consent",
      "tokenUri": "https://oauth2.googleapis.com/token"
    }
  }'
```

*Replace `YOUR_SCOPES` with your required scopes separated by spaces (%20) (e.g., `https://www.googleapis.com/auth/drive`).*

---

## Step 4 — Verify the Architecture

Since Gemini Enterprise handles the user consent flows, securely manages tokens on the user's behalf, and auto-refreshes them, your agent ecosystem relies heavily on this built-in capability.

Your **MCP Server** only needs code to check the `Authorization: Bearer <access_token>` HTTP header passing the valid JWT. No Firestore setup or `/auth` callbacks are needed on the MCP layer.

```bash
# Mocking an ADK Client tool call to your stateless MCP Server
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ya29.a0AfB_bY..." \
  -d '{"tool": "list_files", "arguments": {}}'
```

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `invalid_grant: Token has been expired` | App in Testing mode | Publish app to Production (Step 2c) |
| `redirect_uri_mismatch` | Missing URI in GCP Console | Ensure `vertexaisearch.cloud.google.com/static/oauth/oauth.html` is registered in Step 2d |
| `401 Unauthorized` | Invalid/expired Bearer token | The client failed to refresh the token, or scopes are missing. |

---

## References & Further Reading

* **ADK Event details**: [Handling the Interactive OAuth/OIDC Flow](https://google.github.io/adk-docs/tools-custom/authentication/#2-handling-the-interactive-oauthoidc-flow-client-side)
* **Gemini Enterprise APIs**: [Add an authorization resource to Gemini Enterprise](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent#configure-authorization-details)
