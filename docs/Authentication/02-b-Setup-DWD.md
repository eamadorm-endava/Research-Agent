# Setup Guide — Method 1: Domain-Wide Delegation (DWD)

**Best for:** Google Workspace organisations where a Super Admin is available.  
**User interaction:** None — users never see a consent screen.  
**Requires:** Google Workspace Super Admin access.

---

## Prerequisites

- A GCP project with billing enabled
- A Google Workspace organisation (not personal Gmail)
- A Workspace Super Admin account

---

## Step 1 — Enable Required APIs

In [GCP Console](https://console.cloud.google.com) → **APIs & Services** → **Enable APIs and Services**:

- ✅ Target GCP API (e.g., Google Drive API, BigQuery API)
- ✅ Secret Manager API
- ✅ IAM API

```bash
# Example for Drive
gcloud services enable drive.googleapis.com secretmanager.googleapis.com iam.googleapis.com

# Example for BigQuery
gcloud services enable bigquery.googleapis.com secretmanager.googleapis.com iam.googleapis.com
```

---

## Step 2 — Create the Service Account

```bash
gcloud iam service-accounts create gcp-mcp-dwd-sa \
  --display-name="GCP Service MCP DWD Service Account" \
  --project=YOUR_PROJECT_ID
```

> The SA needs **no GCP IAM roles** — the target GCP service handles permissions via DWD impersonation.

### 2a. Note the Client ID

You will need the **Numeric Client ID** of this SA for Step 5.

```bash
gcloud iam service-accounts describe \
  gcp-mcp-dwd-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --format="value(oauth2ClientId)"
```

---

## Step 3 — Create and Download the SA JSON Key

```bash
gcloud iam service-accounts keys create service-account-key.json \
  --iam-account=gcp-mcp-dwd-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

> [!CAUTION]
> Keep this file secure. Do **not** commit it to source control.

---

## Step 4 — Store the Key in Secret Manager

```bash
# Create the secret
gcloud secrets create gcp-dwd-service-account \
  --project=YOUR_PROJECT_ID

# Add the key as the first version
gcloud secrets versions add gcp-dwd-service-account \
  --data-file=service-account-key.json \
  --project=YOUR_PROJECT_ID

# Delete the local file
rm service-account-key.json
```

### 4a. Grant the MCP's runtime identity access to the secret

If the MCP runs on Cloud Run:

```bash
gcloud secrets add-iam-policy-binding gcp-dwd-service-account \
  --member="serviceAccount:CLOUD_RUN_SA@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=YOUR_PROJECT_ID
```

---

## Step 5 — Enable Domain-Wide Delegation in Workspace Admin Console

> **Requires a Workspace Super Admin account.**

1. Go to [admin.google.com](https://admin.google.com)
2. Navigate to **Security** → **Access and data control** → **API controls**
3. Click **Manage Domain Wide Delegation**
4. Click **Add new** and fill in:
   - **Client ID:** the numeric ID from Step 2a
   - **OAuth Scopes:** Enter the scopes for your target service from the table below:

| Service | Required Scope | Full Scope Documentation |
| :--- | :--- | :--- |
| **Google Drive** | `https://www.googleapis.com/auth/drive` | [Drive Scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth?hl=en#drive-scopes) |
| **BigQuery** | `https://www.googleapis.com/auth/bigquery` | [BigQuery Scopes](https://developers.google.com/identity/protocols/oauth2/scopes#bigquery) |
| **Cloud Storage** | `https://www.googleapis.com/auth/cloud-platform` | [GCS Scopes](https://developers.google.com/identity/protocols/oauth2/scopes#storage) |
| **Google Sheets** | `https://www.googleapis.com/auth/spreadsheets` | [Sheets Scopes](https://developers.google.com/identity/protocols/oauth2/scopes#sheets) |
| **Gmail** | `https://www.googleapis.com/auth/gmail.modify` | [Gmail Scopes](https://developers.google.com/identity/protocols/oauth2/scopes#gmail) |
| **Google Calendar** | `https://www.googleapis.com/auth/calendar` | [Calendar Scopes](https://developers.google.com/identity/protocols/oauth2/scopes#calendar) |

5. Click **Authorize**

---

## Step 6 — Configure the Service MCP Environment Variables

Add the following to your `.env` or Cloud Run service environment:

```env
GOOGLE_CLOUD_PROJECT=your-project-id
DWD_SERVICE_ACCOUNT_SECRET=gcp-dwd-service-account
DWD_DOMAIN=yourcompany.com
```

`DWD_DOMAIN` is optional but recommended — it rejects impersonation requests for users outside your organisation.

---

## Step 7 — Configure the Agent

The agent's `header_provider` must send the user identity with every MCP request.
This is typically wired in `agent.py` via `ctx.session.user_id`:

```python
header_provider=lambda ctx: {
    "Authorization": f"Bearer {get_id_token(SERVICE_URL)}",
    "X-User-Email": ctx.session.user_id or "",
}
```

In **Gemini Enterprise**, `ctx.session.user_id` is automatically set to the authenticated user's email. No extra configuration needed.

---

## Step 8 — Test the Setup

Start the MCP server and call its tools with a valid user identity:

```bash
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "X-User-Email: john@yourcompany.com" \
  -d '{"tool": "list_files", "arguments": {"limit": 5}}'
```

Expected: results accessible to `john@yourcompany.com`.

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `unauthorized_client` | DWD not configured for this SA | Re-check Step 5; wait up to 10 min for propagation |
| `PermissionError: domain mismatch` | User email not in `DWD_DOMAIN` | Update `DWD_DOMAIN` or use the correct email |
| `RuntimeError: GOOGLE_CLOUD_PROJECT not set` | Env var missing | Set `GOOGLE_CLOUD_PROJECT` |
| `403 Forbidden` | User doesn't have access to that resource | Expected — Native ACLs are enforced correctly |
