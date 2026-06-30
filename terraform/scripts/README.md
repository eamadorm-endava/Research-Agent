# Master Deployment Guide (Creation Manager)

This directory contains the orchestration scripts required to automatically provision, configure, and deploy the entire Research-Agent ecosystem.

The central entry point is **`creation_manager.sh`**, which orchestrates the complete lifecycle: bootstrapping Terraform, deploying shared infrastructure, generating CI/CD pipelines, deploying MCP Servers, and provisioning the Vertex AI Agent Engine.

---

## 1. Prerequisites (Manual Steps)

Before executing the orchestrator, you **must** manually set up a few configurations in your Google Cloud Project.

### A. Enable Required APIs
For a completely new project, you must enable the core APIs before you can configure connections or secrets.
1. Open the Cloud Shell or your local terminal authenticated to GCP.
2. Run the following command to enable Cloud Build and Secret Manager:
   ```bash
   gcloud services enable cloudbuild.googleapis.com secretmanager.googleapis.com
   ```

### B. Cloud Build GitHub Connection
Cloud Build requires explicit permission to read from your repository to generate the CI/CD triggers.
1. Navigate to **Cloud Build > Repositories** in the Google Cloud Console.
2. Select the **2nd gen** tab and click **Create Host Connection**.
3. Follow the OAuth prompts to connect your GitHub account.
4. Once connected, click **Link Repository** and select the Research-Agent repository.
5. Note down the **Connection Name** (e.g., `github-conn`) and the **Repository Slug** (e.g., `eamadorm-endava/Research-Agent`). You will pass these to the orchestrator.

### C. Setup OAuth Clients
The Gemini Enterprise Agent requires OAuth credentials to act on behalf of the user to access external systems securely.

**Google OAuth:**
1. Go to **APIs & Services > OAuth consent screen**. If it's your first time, you must configure the consent screen (User Type: Internal or External, add basic app details).
2. Go to **APIs & Services > Credentials**.
3. Click **Create Credentials > OAuth client ID** (Application type: Web application).
4. Add the following three **Authorized redirect URIs**:
   - `http://localhost:8000/dev-ui/`
   - `https://vertexaisearch.cloud.google.com/oauth-redirect`
   - `https://vertexaisearch.cloud.google.com/static/oauth/oauth.html`
5. Note down the **Client ID** and **Client Secret**.

**Microsoft OAuth (For OneDrive/SharePoint/Outlook):**
1. Go to the Azure Portal > **App registrations** and create a new application.
2. Add the same three redirect URIs as above (Web platform type).
3. Note down the **Application (client) ID** and generate a **Client secret**.

### D. Populate Secret Manager
The CI/CD pipelines expect your sensitive secrets to be available in Google Cloud Secret Manager.
Create the following secrets manually in your GCP project:
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `MICROSOFT_OAUTH_CLIENT_ID`
- `MICROSOFT_OAUTH_CLIENT_SECRET`
- `ATLASSIAN_CREDENTIALS`

---

## 2. Executing the Orchestrator

Once the prerequisites are complete, you can execute the master orchestration script.

### Command Format
Run this from the root of the repository:

```bash
bash terraform/scripts/creation_manager.sh \
    --project "p-dev-gce-60pf" \
    --region "us-central1" \
    --sa-name "terraform-sa" \
    --admin-user-email "emmanuel.amador@endava.com" \
    --github-connection-name "eamadorm-github-connection" \
    --repository-slug " eamadorm-endava-Research-Agent" \
    --mcp-servers-to-deploy "all" \
    --ge-app-location "global" \
    --deploy-bootstrap "true" \
    --deploy-shared-resources "true" \
    --deploy-mcp-servers "true" \
    --deploy-ekb-pipeline "true" \
    --deploy-ge-app "true" \
    --deploy-ai-agent "true"
```

### What happens next?
1. **Pre-flight summary**: The script will print a summary of what it computed and pause for your confirmation (`y/N`).
2. **Infrastructure Deployment**: It will bootstrap Terraform, create the shared infrastructure (GCS Landing Zone, Secret bindings), and automatically create all Cloud Build Triggers for the entire ecosystem.
3. **Trigger Execution**: It will programmatically trigger the Cloud Build pipelines to deploy the dynamically discovered array of MCP servers and the EKB pipeline.
4. **Agent Registration**: Finally, it will create the Gemini Enterprise Data Store, trigger the AI Agent pipeline, and register the agent dynamically.

**No manual CI/CD intervention or hardcoded URLs are required!**

---

## Appendix: Legacy Scripts
Note: This orchestrator replaces legacy manual scripts such as `run_once.sh` and individual `bootstrap.sh` executions, consolidating them into a single, unified pipeline.