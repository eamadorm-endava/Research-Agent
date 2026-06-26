#!/bin/bash
# scripts/creation_manager.sh

# Exit on error
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# -----------------------------------------------------------------------------
# Master Creation Orchestrator
# -----------------------------------------------------------------------------
# This script orchestrates the deployment of all resources in the project.
#
# Usage: ./terraform/scripts/creation_manager.sh [OPTIONS]
#
# ## Global Parameters
#   --project                    GCP Project ID (Required).
#   --region                     GCP Region (Required).
#
# ## Bootstrap Parameters
#   --deploy-bootstrap           Set to "true" to run bootstrap.sh.
#   --sa-name                    Terraform Service Account Name (Required for Bootstrap).
#   --admin-user-email           Admin Email for local impersonation (Required for Bootstrap).
#   --developer-group-email      Developer Group Email for impersonation (Required for Bootstrap).
#   --github-connection-name     GitHub Connection Name in Cloud Build (Required for Bootstrap).
#   --repository-slug            GitHub Repository Slug (e.g. owner-repo) (Required for Bootstrap).
#
# ## Shared Resources Parameters
#   --deploy-shared-resources    Set to "true" to deploy Shared Resources.
#
# ## Gemini Enterprise Parameters
#   --deploy-ge-app              Set to "true" to deploy a Gemini Enterprise App.
#   --ge-app-location            Location for the Gemini Enterprise App ("global", "us", or "eu").
#   --ge-app-name-suffix         Unique suffix for the GE App ID (Optional, defaults to "osiris-app").
#
# ## AI Agent Parameters
#   --deploy-ai-agent            Set to "true" to deploy AI Agent resources.
#   --agent-engine-location      Location for the Vertex AI Agent Engine (e.g., "us-central1").
#
# ## MCP Servers Parameters
#   --deploy-mcp-servers         Set to "true" to deploy MCP servers.
#   --mcp-servers-to-deploy      Comma-separated list of MCP servers (e.g., "gcs=us-east1,bq") or "all" to deploy all MCP servers.
#
# ## Pipelines Parameters
#   --deploy-ekb-pipeline        Set to "true" to deploy the EKB pipeline.
#
# ## CI/CD Parameters
#   --force-recreate             Set to "true" to delete and recreate triggers if they exist.
#
# -----------------------------------------------------------------------------

# --- Global Configuration ---
PROJECT_ID=""
REGION=""

# --- Bootstrap Parameters ---
DEPLOY_BOOTSTRAP="false"
SA_NAME="terraform-sa-gemini-project"
ADMIN_USER_EMAIL="emmanuel.amador@endava.com"
DEVELOPER_GROUP_EMAIL="gcu_latam_team_devs@endava.com"
GITHUB_CONNECTION_NAME="eamadorm-github-connection"
REPOSITORY_SLUG="eamadorm-endava-Research-Agent"

# --- Shared Resources Parameters ---
DEPLOY_SHARED_RESOURCES="false"

# --- Gemini Enterprise Parameters ---
DEPLOY_GE_APP="false"
GE_APP_LOCATION=""
GE_APP_NAME_SUFFIX="osiris-app"

# --- AI Agent Parameters ---
DEPLOY_AI_AGENT="false"
AGENT_ENGINE_LOCATION=""

# --- MCP Servers Parameters ---
DEPLOY_MCP_SERVERS="false"
MCP_SERVERS_TO_DEPLOY="all"

# --- Pipelines Parameters ---
DEPLOY_EKB_PIPELINE="false"

# --- CI/CD Parameters ---
FORCE_RECREATE="false"


# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        # Global
        --project) PROJECT_ID="$2"; shift ;;
        --region) REGION="$2"; shift ;;
        
        # Bootstrap
        --deploy-bootstrap) DEPLOY_BOOTSTRAP="$2"; shift ;;
        --sa-name) SA_NAME="$2"; shift ;;
        --admin-user-email) ADMIN_USER_EMAIL="$2"; shift ;;
        --developer-group-email) DEVELOPER_GROUP_EMAIL="$2"; shift ;;
        --github-connection-name) GITHUB_CONNECTION_NAME="$2"; shift ;;
        --repository-slug) REPOSITORY_SLUG="$2"; shift ;;
        
        # Shared Resources
        --deploy-shared-resources) DEPLOY_SHARED_RESOURCES="$2"; shift ;;
        
        # Gemini Enterprise
        --deploy-ge-app) DEPLOY_GE_APP="$2"; shift ;;
        --ge-app-location) GE_APP_LOCATION="$2"; shift ;;
        --ge-app-name-suffix) GE_APP_NAME_SUFFIX="$2"; shift ;;
        
        # AI Agent
        --deploy-ai-agent) DEPLOY_AI_AGENT="$2"; shift ;;
        --agent-engine-location) AGENT_ENGINE_LOCATION="$2"; shift ;;
        
        # MCP Servers
        --deploy-mcp-servers) DEPLOY_MCP_SERVERS="$2"; shift ;;
        --mcp-servers-to-deploy) MCP_SERVERS_TO_DEPLOY="$2"; shift ;;
        
        # Pipelines
        --deploy-ekb-pipeline) DEPLOY_EKB_PIPELINE="$2"; shift ;;
        
        # CI/CD
        --force-recreate) FORCE_RECREATE="$2"; shift ;;
        
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Validation
if [[ -z "$PROJECT_ID" ]] || [[ -z "$REGION" ]]; then
    echo "Error: Global parameters are required (--project, --region)."
    exit 1
fi

if [[ "$DEPLOY_BOOTSTRAP" == "true" ]]; then
    if [[ -z "$SA_NAME" ]] || [[ -z "$ADMIN_USER_EMAIL" ]] || [[ -z "$DEVELOPER_GROUP_EMAIL" ]] || [[ -z "$GITHUB_CONNECTION_NAME" ]] || [[ -z "$REPOSITORY_SLUG" ]]; then
        echo "Error: --deploy-bootstrap is true, but missing required parameters."
        echo "Required: --sa-name, --admin-user-email, --developer-group-email, --github-connection-name, --repository-slug"
        exit 1
    fi
fi

if [[ -z "$AGENT_ENGINE_LOCATION" ]]; then
    AGENT_ENGINE_LOCATION="$REGION"
fi

if [[ "$DEPLOY_GE_APP" == "true" ]]; then
    if [ -z "$GE_APP_LOCATION" ]; then
        echo "Error: --deploy-ge-app is true, but missing required parameters."
        echo "Required: --ge-app-location"
        exit 1
    fi
    
    if [[ "$GE_APP_LOCATION" != "global" ]] && [[ "$GE_APP_LOCATION" != "us" ]] && [[ "$GE_APP_LOCATION" != "eu" ]]; then
        echo "Error: --ge-app-location must be one of: 'global', 'us', or 'eu'."
        exit 1
    fi
fi

if [[ "$DEPLOY_AI_AGENT" == "true" ]]; then
    if [ -z "$AGENT_ENGINE_LOCATION" ]; then
        echo "Error: --deploy-ai-agent is true, but missing required parameters."
        echo "Required: --agent-engine-location"
        exit 1
    fi
fi

if [[ "$DEPLOY_MCP_SERVERS" == "true" ]]; then
    if [[ -z "$MCP_SERVERS_TO_DEPLOY" ]]; then
        echo "Error: --deploy-mcp-servers is true, but --mcp-servers-to-deploy is missing."
        exit 1
    fi
fi
# Pre-compute variables for summary and execution
if [[ "$DEPLOY_GE_APP" == "true" ]] || [[ "$DEPLOY_AI_AGENT" == "true" ]]; then
    GE_APP_ID="${PROJECT_ID}-${GE_APP_LOCATION}-${GE_APP_NAME_SUFFIX}"
    AGENT_DISPLAY_NAME=$(grep -E '^[[:space:]]+_AGENT_DISPLAY_NAME:' "$REPO_ROOT/terraform/ai_agent_resources/ai-agent-services-cloud-build-cd.yaml" | sed -E 's/.*_AGENT_DISPLAY_NAME:[[:space:]]*"([^"]+)".*/\1/')
fi

# Summary
echo "================================================================="
echo "MASTER CREATION ORCHESTRATOR"
echo "================================================================="
echo "Target Project: $PROJECT_ID"
echo "Default Region: $REGION"
echo ""
echo "You have requested the following deployments:"
echo "Bootstrap: $DEPLOY_BOOTSTRAP"
echo "Shared Resources: $DEPLOY_SHARED_RESOURCES"
echo "Gemini Enterprise App: $DEPLOY_GE_APP"
if [[ "$DEPLOY_GE_APP" == "true" ]]; then
    echo "  - GE App Location: $GE_APP_LOCATION"
    echo "  - GE App ID: $GE_APP_ID"
fi
echo "AI Agent Resources: $DEPLOY_AI_AGENT"
if [[ "$DEPLOY_AI_AGENT" == "true" ]]; then
    echo "  - Agent Engine Location: $AGENT_ENGINE_LOCATION"
    echo "  - Agent Display Name: $AGENT_DISPLAY_NAME"
fi
echo "MCP Servers: $DEPLOY_MCP_SERVERS"
if [[ "$DEPLOY_MCP_SERVERS" == "true" ]]; then
    echo "  - Servers to Deploy: $MCP_SERVERS_TO_DEPLOY"
fi
echo "EKB Pipeline: $DEPLOY_EKB_PIPELINE"
echo "================================================================="
read -p "Are you absolutely sure you want to proceed with these deployments? (y/N): " confirm

if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "Deployment cancelled."
    exit 0
fi

echo "-----------------------------------------------------------------"
echo "Configuring gcloud project..."
gcloud config set project "$PROJECT_ID"
echo "-----------------------------------------------------------------"

# 1. Bootstrap
if [[ "$DEPLOY_BOOTSTRAP" == "true" ]]; then
    echo "STEP 1: Run Bootstrap"
    echo "-----------------------------------------------------------------"
    bash "$SCRIPT_DIR/bootstrap.sh" \
        --project "$PROJECT_ID" \
        --location "$REGION" \
        --sa-name "$SA_NAME" \
        --admin-user-email "$ADMIN_USER_EMAIL" \
        --developer-group-email "$DEVELOPER_GROUP_EMAIL"
    echo "Bootstrap complete."
else
    echo "Skipping Bootstrap."
fi

# 2. Shared Resources
if [[ "$DEPLOY_SHARED_RESOURCES" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 2: Deploy Shared Resources"
    echo "-----------------------------------------------------------------"
    BUCKET_NAME="${PROJECT_ID}-terraform-state"
    pushd "$REPO_ROOT/terraform/shared_resources" >/dev/null
    terraform init -reconfigure \
        -backend-config="bucket=${BUCKET_NAME}" \
        -backend-config="prefix=terraform/state/shared-resources"
    terraform plan -var="project_id=$PROJECT_ID" -var="main_region=$REGION"
    terraform apply -auto-approve -var="project_id=$PROJECT_ID" -var="main_region=$REGION"
    popd >/dev/null
else
    echo "Skipping Shared Resources deployment."
fi

# 3. Create CI/CD Triggers
echo "-----------------------------------------------------------------"
echo "STEP 3: Create CI/CD Triggers"
echo "-----------------------------------------------------------------"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
export GITHUB_CONNECTION_NAME="$GITHUB_CONNECTION_NAME"
export REPOSITORY_SLUG="$REPOSITORY_SLUG"

# Compute AI Agent URLs to explicitly inject into triggers
BQ_REGION="$REGION"
GCS_REGION="$REGION"
DRIVE_REGION="$REGION"
CALENDAR_REGION="$REGION"
ONEDRIVE_REGION="$REGION"
ATLASSIAN_REGION="$REGION"
SHAREPOINT_REGION="$REGION"
OUTLOOK_REGION="$REGION"

if [[ "$MCP_SERVERS_TO_DEPLOY" != "all" ]]; then
    IFS=',' read -ra SERVER_LIST <<< "$MCP_SERVERS_TO_DEPLOY"
    for SERVER_ENTRY in "${SERVER_LIST[@]}"; do
        if [[ "$SERVER_ENTRY" =~ ^([^=]+)=([^=]+)$ ]]; then
            SERVER_BASE="${BASH_REMATCH[1]}"
            SERVER_REGION="${BASH_REMATCH[2]}"
            case "$SERVER_BASE" in
                bq) BQ_REGION="$SERVER_REGION" ;;
                gcs) GCS_REGION="$SERVER_REGION" ;;
                drive) DRIVE_REGION="$SERVER_REGION" ;;
                calendar) CALENDAR_REGION="$SERVER_REGION" ;;
                onedrive) ONEDRIVE_REGION="$SERVER_REGION" ;;
                atlassian) ATLASSIAN_REGION="$SERVER_REGION" ;;
                sharepoint) SHAREPOINT_REGION="$SERVER_REGION" ;;
                outlook) OUTLOOK_REGION="$SERVER_REGION" ;;
            esac
        fi
    done
fi

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
BQ_URL="https://bigquery-mcp-server-${PROJECT_NUMBER}.${BQ_REGION}.run.app"
GCS_URL="https://gcs-mcp-server-${PROJECT_NUMBER}.${GCS_REGION}.run.app"
DRIVE_URL="https://drive-mcp-server-${PROJECT_NUMBER}.${DRIVE_REGION}.run.app"
CALENDAR_URL="https://calendar-mcp-server-${PROJECT_NUMBER}.${CALENDAR_REGION}.run.app"
ONEDRIVE_URL="https://onedrive-mcp-server-${PROJECT_NUMBER}.${ONEDRIVE_REGION}.run.app"
ATLASSIAN_URL="https://atlassian-mcp-server-${PROJECT_NUMBER}.${ATLASSIAN_REGION}.run.app"
SHAREPOINT_URL="https://sharepoint-mcp-server-${PROJECT_NUMBER}.${SHAREPOINT_REGION}.run.app"
OUTLOOK_URL="https://outlook-mcp-server-${PROJECT_NUMBER}.${OUTLOOK_REGION}.run.app"
EKB_URL="https://ekb-pipeline-${PROJECT_NUMBER}.${REGION}.run.app"

bash "$SCRIPT_DIR/cicd_triggers_creation.sh" \
    --region "$REGION" \
    --deploy-mcp-servers "$DEPLOY_MCP_SERVERS" \
    --mcp-servers-to-deploy "$MCP_SERVERS_TO_DEPLOY" \
    --deploy-ekb-pipeline "$DEPLOY_EKB_PIPELINE" \
    --deploy-ai-agent "$DEPLOY_AI_AGENT" \
    --ge-app-location "$GE_APP_LOCATION" \
    --ge-app-name-suffix "$GE_APP_NAME_SUFFIX" \
    --bq-url "$BQ_URL" \
    --gcs-url "$GCS_URL" \
    --drive-url "$DRIVE_URL" \
    --calendar-url "$CALENDAR_URL" \
    --onedrive-url "$ONEDRIVE_URL" \
    --atlassian-url "$ATLASSIAN_URL" \
    --sharepoint-url "$SHAREPOINT_URL" \
    --outlook-url "$OUTLOOK_URL" \
    --ekb-pipeline-url "$EKB_URL" \
    --force-recreate "$FORCE_RECREATE"

# 4. MCP Servers
if [[ "$DEPLOY_MCP_SERVERS" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 4: Deploy MCP Servers via Cloud Build Triggers"
    echo "-----------------------------------------------------------------"
    
    SERVER_LIST=()
    if [[ "$MCP_SERVERS_TO_DEPLOY" == "all" ]]; then
        SERVER_LIST=("bq" "gcs" "drive" "calendar" "onedrive")
    else
        IFS=',' read -ra SERVER_LIST <<< "$MCP_SERVERS_TO_DEPLOY"
    fi

    for SERVER_ENTRY in "${SERVER_LIST[@]}"; do
        if [[ "$SERVER_ENTRY" =~ ^([^=]+)=([^=]+)$ ]]; then
            SERVER_BASE="${BASH_REMATCH[1]}"
            SERVER_REGION="${BASH_REMATCH[2]}"
        else
            SERVER_BASE="$SERVER_ENTRY"
            SERVER_REGION="$REGION"
        fi
        
        TRIGGER_NAME="${SERVER_BASE}-mcp-server-services-apply"
        echo "Triggering Cloud Build for ${SERVER_BASE} MCP server in ${SERVER_REGION}: ${TRIGGER_NAME}"
        
        if gcloud builds triggers describe "${TRIGGER_NAME}" --region="${REGION}" >/dev/null 2>&1; then
            gcloud builds triggers run "${TRIGGER_NAME}" --region="${REGION}" --branch="main" || echo "Warning: Failed to run trigger ${TRIGGER_NAME}."
        else
            echo "Warning: Trigger ${TRIGGER_NAME} not found. Skipping."
        fi
    done
else
    echo "Skipping MCP Servers deployment."
fi

# 5. EKB Pipeline
if [[ "$DEPLOY_EKB_PIPELINE" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 5: Deploy EKB Pipeline Resources"
    echo "-----------------------------------------------------------------"
    TRIGGER_NAME="ekb-pipeline-services-apply"
    if gcloud builds triggers describe "${TRIGGER_NAME}" --region="${REGION}" >/dev/null 2>&1; then
        echo "Triggering Cloud Build for EKB Pipeline: ${TRIGGER_NAME}"
        gcloud builds triggers run "${TRIGGER_NAME}" --region="${REGION}" --branch="main" || echo "Warning: Failed to run EKB Pipeline trigger."
    else
        echo "Warning: Trigger ${TRIGGER_NAME} not found. Skipping."
    fi
else
    echo "Skipping EKB Pipeline Resources deployment."
fi


# 6. Gemini Enterprise App
if [[ "$DEPLOY_GE_APP" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 6: Deploy Gemini Enterprise App"
    echo "-----------------------------------------------------------------"
    
    # Enable dialogflow API which is required to create engines
    echo "Ensuring dialogflow API is enabled..."
    gcloud services enable dialogflow.googleapis.com
    
    echo "Creating Gemini Enterprise App (Engine) with ID: $GE_APP_ID..."
    bash "$REPO_ROOT/terraform/ai_agent_resources/scripts/ge_agent_manager.sh" create-ge-app \
        --project "$PROJECT_ID" \
        --ge-location "$GE_APP_LOCATION" \
        --ge-app-id "$GE_APP_ID"
    
    echo "Gemini Enterprise App creation completed."
else
    echo "Skipping Gemini Enterprise App deployment."
fi

# 7. AI Agent
if [[ "$DEPLOY_AI_AGENT" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 7: Deploy AI Agent Resources"
    echo "-----------------------------------------------------------------"
    
    # Trigger Cloud Build for Agent deployment
    TRIGGER_NAME="ai-agent-services-apply"
    if gcloud builds triggers describe "${TRIGGER_NAME}" --region="${REGION}" >/dev/null 2>&1; then
        echo "Triggering Cloud Build for AI Agent: ${TRIGGER_NAME}"
        gcloud builds triggers run "${TRIGGER_NAME}" \
            --region="${REGION}" \
            --branch="main" || echo "Warning: Failed to run AI Agent trigger."
    else
        echo "Warning: Trigger ${TRIGGER_NAME} not found. Ensure CI/CD triggers are created."
    fi
else
    echo "Skipping AI Agent deployment."
fi

echo "================================================================="
echo "ORCHESTRATION COMPLETE."
echo "================================================================="
