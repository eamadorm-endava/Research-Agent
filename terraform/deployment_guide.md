# Deployment Guide

This guide walks you through deploying the Research-Agent project, including prerequisites, automated orchestration via `creation_manager.sh`, and the final manual setup steps.

## Phase 1: Initial Manual Steps

Before executing any automated scripts, ensure your GCP project is properly prepared:

1. **Enable Essential APIs**
   Enable the Cloud Build API and Secret Manager API:
   ```bash
   gcloud services enable cloudbuild.googleapis.com secretmanager.googleapis.com
   ```

2. **Cloud Build Service Agent Permissions**
   Grant the Secret Manager Admin role to the Cloud Build Service Agent so it can read/write secrets (e.g. GitHub tokens):
   ```bash
   PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format='value(projectNumber)')
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
       --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-cloudbuild.iam.gserviceaccount.com" \
       --role="roles/secretmanager.admin"
   ```

3. **GitHub Repository Connection**
   - Navigate to **Cloud Build > Triggers > Manage Repositories** in the GCP Console.
   - Connect your GitHub Repository to Cloud Build using the 2nd Gen integration.

4. **OAuth Consent Screen**
   - Go to **APIs & Services > OAuth consent screen**.
   - Choose **Internal** (if deploying within a Google Workspace) or **External** depending on your target audience.
   - Fill in the required App information (Name, Support Email, Developer Contact).

5. **OAuth 2.0 Client Credentials**
   - Go to **APIs & Services > Credentials**.
   - Click **Create Credentials > OAuth client ID**.
   - Application type: **Web application**.
   - Add the[ Authorized Redirect URI for Gemini Enterprise](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent?hl=en#authorize-your-agent):
     - `https://vertexaisearch.cloud.google.com/static/oauth/oauth.html`
     - `https://vertexaisearch.cloud.google.com/oauth-redirect`
   - Save the Client ID and Client Secret.

6. **Store Credentials in Secret Manager**
   Save the generated credentials into GCP Secret Manager to be used securely by the pipelines. Additionally, define the Gemini Enterprise Auth IDs that will uniquely identify the OAuth integrations for your agent:
   ```bash
   echo -n "YOUR_CLIENT_ID" | gcloud secrets create GOOGLE_OAUTH_CLIENT_ID --data-file=-
   echo -n "YOUR_CLIENT_SECRET" | gcloud secrets create GOOGLE_OAUTH_CLIENT_SECRET --data-file=-
   
   # Define the names for your Gemini Enterprise Auth Integrations
   echo -n "mock-gemini-enterprise-auth-id-resource" | gcloud secrets create GEMINI_GOOGLE_AUTH_ID --data-file=-
   
   # Optional: Only required if you are deploying Microsoft Integrations (e.g., OneDrive)
   # echo -n "mock-gemini-enterprise-auth-id-resource2" | gcloud secrets create GEMINI_MICROSOFT_AUTH_ID --data-file=-
   ```

## Phase 2: Automated Orchestration (creation_manager.sh)

Once the prerequisites are complete, use the `creation_manager.sh` script to trigger the Cloud Build pipelines and deploy your components automatically. This script handles the bootstrap, shared resources, and all specified component deployments.

The orchestrator relies on boolean flags (`true`/`false`) to selectively deploy the MCP servers, EKB Pipeline, and the AI Agent.

### Usage Example

```bash
./terraform/scripts/creation_manager.sh \
    --project YOUR_PROJECT_ID \
    --region mock-region \
    --deploy-bootstrap true \
    --sa-name "name-of-sa-that-will-run-terraform-and-CICD-pipelines" \
    --user-email "user@example.com" \
    --developer-group-email "developers@example.com" \
    --github-connection-name "my-github-connection" \
    --repository-slug "owner-repo" \
    --deploy-shared-resources true \
    --deploy-ge-app true \
    --ge-app-location mock-location \
    --ge-app-name-suffix mock-app-suffix \
    --deploy-mcp-servers true \
    --mcp-servers-to-deploy bq,gcs,drive,calendar,onedrive \
    --deploy-ekb-pipeline true \
    --deploy-ai-agent true \
    --agent-engine-location mock-location \
    --force-recreate false
```

### What happens under the hood?

1. **Bootstrap & Shared Resources**: Sets up the IAM roles, service accounts, buckets, and then applies the shared Terraform resources (Artifact Registry, etc).
2. **CI/CD Triggers & Runtime Variable Injection**: 
   - Dynamically creates the Cloud Build triggers only for the selected components.
   - **Important Consideration**: The orchestrator automatically computes dynamic endpoints (e.g., Cloud Run URLs for MCP servers, Gemini Enterprise App IDs, and Regions) and *injects them directly into the Cloud Build triggers as substitution variables*. 
   - These injected variables **completely override** any static/dummy values present in the `cloud-build-cd.yaml` files, ensuring that the deployed AI Agent always points to the exact infrastructure instantiated during that specific run without risk of configuration mismatches.
3. **MCP Servers & EKB Pipeline**: The script executes `gcloud builds triggers run` to invoke the CD pipelines.
   - **Note on Commit SHAs**: Even though the pipeline is triggered manually via a script (and not a GitHub webhook), Cloud Build automatically resolves the HEAD commit of the target branch (`main`) and dynamically populates standard built-in variables like `$COMMIT_SHA` and `$SHORT_SHA`, ensuring your tagging operations work flawlessly.
4. **Gemini Enterprise App**: 
   - The script creates the Gemini Enterprise App via the Discovery Engine API using the computed ID (e.g. `<project>-<location>-<suffix>`).
5. **AI Agent Deployment & Model Armor**: 
   - The orchestrator seamlessly provisions the `security-template` Model Armor template codified directly via Terraform with advanced safety validations configured.
   - It triggers the AI Agent Cloud Build CD pipeline, seamlessly passing down the dynamically created `GE_APP_ID` and region, along with all computed dependency infrastructure endpoints (such as the deployed MCP Server URLs and the EKB pipeline URL) through the pre-configured Cloud Build trigger substitutions. This ensures the Agent is accurately linked to all of its dependent services.

## Phase 3: Final Manual Steps

Once the automated deployment completes successfully:

1. **Configure Gemini Enterprise Access Control**
   - Navigate to **Agent Builder** in the GCP Console.
   - Select the newly created App (e.g., `osiris-ai-agent`).
   - Navigate to **Data store access control** (or similar identity settings based on your App type).
   - Manually add the Google Identity Provider (e.g., your Google Workspace organization).
   
2. **Grant User Access**
   - Ensure the intended users of the App are granted appropriate access so they can interact with the Intranet Search App and the registered AI Agent.

## Phase 4: Automated Destruction (deletion_manager.sh)

If you need to tear down the environment, you can use the `deletion_manager.sh` orchestrator. The orchestrator is designed to resolve dependencies securely (e.g. deleting the AI Agent auth tokens before deleting the GE App) and avoids destroying global components by accident.

### Usage Example

```bash
./terraform/scripts/deletion_manager.sh \
    --project YOUR_PROJECT_ID \
    --region us-central1 \
    --delete-ai-agent true \
    --agent-engine-location us-central1 \
    --delete-ge-app true \
    --ge-location global \
    --ge-app-name-suffix osiris-app \
    --delete-mcp-servers true \
    --delete-ekb-pipeline true \
    --delete-shared-resources false \
    --delete-bootstrap false
```

### Deletion Rules
- **AI Agent vs GE App**: The orchestrator handles unregistering the AI Agent's authentication tokens from Gemini Enterprise *before* destroying the AI Agent infrastructure. If you choose to delete both, it deletes the AI Agent before attempting to destroy the GE Engine to prevent HTTP 404 mismatch errors.
- **Dry Run Summary**: The script will dynamically compute and display all the target resources (including the exact `GE_APP_ID`) and require a final `(y/N)` confirmation before executing any destructive operations.
