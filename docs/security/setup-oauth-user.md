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
- ✅ Secret Manager API

```bash
# Replace <api-name> with drive.googleapis.com, bigquery.googleapis.com, etc.
gcloud services enable <api-name>.googleapis.com secretmanager.googleapis.com
```

---

## Step 2 — Create OAuth 2.0 Credentials

Setting up OAuth involves configuring the **Consent Screen** (the page users see when logging in) and the **Client ID** (the unique identity for your MCP server).

### 2a. Initiate Client Creation
1. In the GCP Console, navigate to **APIs & Services** → **Credentials**.
2. Click **Create Credentials** → **OAuth client ID**.
3. Select **Web application** as the application type.
4. If you see the message *"To create an OAuth client ID, you must first configure your consent screen"*:
    - Click **Configure Consent Screen**.
    - Choose **User Type** (**Internal** for Workspace orgs, **External** for personal accounts).
    - Fill in the required fields (**App name**, **User support email**, **Developer contact email**).
    - Click **Save and Continue**.

### 2b. Add Scopes (Data Access)
1. In the **Scopes** (Data Access) section of the Consent Screen configuration, click **Add or remove scopes**.
2. Search for and add the necessary scopes for your target service.

| Service | Required Scope | Full Scope Documentation |
| :--- | :--- | :--- |
| **Google Drive** | `https://www.googleapis.com/auth/drive` | [Drive Scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth?hl=en#drive-scopes) |
| **BigQuery** | `https://www.googleapis.com/auth/bigquery` | [BigQuery Scopes](https://developers.google.com/identity/protocols/oauth2/scopes#bigquery) |
| **Cloud Storage** | `https://www.googleapis.com/auth/cloud-platform` | [GCS Scopes](https://developers.google.com/identity/protocols/oauth2/scopes#storage) |
| **Google Sheets** | `https://www.googleapis.com/auth/spreadsheets` | [Sheets Scopes](https://developers.google.com/identity/protocols/oauth2/scopes#sheets) |
| **Gmail** | `https://www.googleapis.com/auth/gmail.modify` | [Gmail Scopes](https://developers.google.com/identity/protocols/oauth2/scopes#gmail) |
| **Google Calendar** | `https://www.googleapis.com/auth/calendar` | [Calendar Scopes](https://developers.google.com/identity/protocols/oauth2/scopes#calendar) |

3. Click **Update** → **Save and Continue**.

### 2c. Publish App
1. On the final summary page, click **Back to Dashboard** or go to **OAuth consent screen**.
2. Click **Publish App** and confirm. This prevents refresh tokens from expiring after 7 days.

### 2d. Finalize and Download Client JSON
1. Return to **APIs & Services** → **Credentials**.
2. Click **Create Credentials** → **OAuth client ID** again (if not already completed).
3. **Application type**: `Web application`.
4. **Name**: `GCP Services MCP OAuth Client`.
5. **Authorized redirect URIs**:
    - Local dev: `http://localhost:8080/oauth2callback`
    - Production: `https://your-mcp-service.run.app/oauth2callback`

> [!NOTE]
> **What is a Redirect URI?**  
> This is a security feature. It is the URL Google will send the user back to after they grant permission. It **must exactly match** the `OAUTH_REDIRECT_URI` environment variable in your server configuration.

6. Click **Create**.
7. In the confirmation dialog, click **Download JSON**. This file contains your client configuration for the next step.

---

## Step 3 — Store the Client Secret in Secret Manager

The MCP server does not store credentials on disk for security. You must upload the JSON file you just downloaded to GCP Secret Manager.

```bash
# 1. Create the secret container
gcloud secrets create gcp-oauth-credentials \
  --project=YOUR_PROJECT_ID

# 2. Add the downloaded JSON file as the first version
gcloud secrets versions add gcp-oauth-credentials \
  --data-file=client_secret_YOUR_CLIENT_ID.json \
  --project=YOUR_PROJECT_ID

# 3. Securely delete the local JSON file
rm client_secret_*.json
```

### 5a. Grant the MCP runtime access to the secret

For the MCP server to read this secret at startup, its service account (the one running the Cloud Run service) needs the `Secret Accessor` role.

```bash
gcloud secrets add-iam-policy-binding gcp-oauth-credentials \
  --member="serviceAccount:CLOUD_RUN_SA@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=YOUR_PROJECT_ID
```

For local development, grant your personal account:

```bash
gcloud secrets add-iam-policy-binding gcp-oauth-credentials \
  --member="user:your-email@example.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=YOUR_PROJECT_ID
```

---

## Step 4 — Configure the MCP Environment Variables

```env
GOOGLE_CLOUD_PROJECT=your-project-id
OAUTH_SECRET_NAME=gcp-oauth-credentials
OAUTH_REDIRECT_URI=https://your-mcp-service.run.app/oauth2callback
MCP_HOST=0.0.0.0
MCP_PORT=8080
```

For **local development**: `OAUTH_REDIRECT_URI=http://localhost:8080/oauth2callback`

---

## Step 5 — (Production) Set Up Firestore for Token Persistence

By default tokens are stored in memory and lost on server restart. For production, store them in Firestore.

```bash
# Enable Firestore and grant access
gcloud services enable firestore.googleapis.com
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:CLOUD_RUN_SA@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/datastore.user"
```

> The MCP's Firestore token store saves tokens keyed by the user identity, so each user authenticates once and never needs to repeat the process.

---

## Step 6 — User Authentication Flow

### First time (one-time per user)

1. Start the MCP server
2. User is directed to: `GET /auth`
3. User completes Google consent
4. Tokens are stored in Firestore/Memory

### Subsequent requests (transparent)

- The `access_token` is used for GCP API calls.
- Expired tokens are refreshed automatically via `refresh_token`.

---

## Step 7 — Configure the Agent

In `agent.py`, the `header_provider` must pass the user identity:

```python
header_provider=lambda ctx: {
    "Authorization": f"Bearer {get_id_token(SERVICE_URL)}",
    "X-User-Email": ctx.session.user_id or "",
}
```

---

## Step 8 — Test the Setup

1. Start the server (e.g., `uv run --group mcp-drive python -m mcp_servers.google_drive.app.main`)
2. Authenticate: Open `http://localhost:8080/auth` in your browser.
3. Call a tool:
```bash
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "X-User-Email: your-email@gmail.com" \
  -d '{"tool": "list_files", "arguments": {"limit": 5}}'
```

---

## Token Expiry Reference

| Token | Expires | Auto-renewed? |
|---|---|---|
| Access token | ~1 hour | ✅ Yes |
| Refresh token | Never* | ✅ N/A |

*Unless the user revokes access or the token is unused for 6 months.

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `invalid_grant: Missing code verifier` | New Flow object created on callback | Reuse `_pending_flow` from `/auth` (already fixed) |
| `invalid_grant: Token has been expired` | App in Testing mode | Publish app to Production (Step 2c) |
| `Authorization code not found` | User accessed `/oauth2callback` directly | Always start from `/auth` |
| `Could not load OAuth client config` | Secret not found or permission denied | Check Secret Manager secret name and IAM binding |
