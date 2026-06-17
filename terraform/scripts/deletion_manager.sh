#!/bin/bash
# scripts/deletion_manager.sh

# Exit on error
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# -----------------------------------------------------------------------------
# Master Deletion Orchestrator
# -----------------------------------------------------------------------------
# This script orchestrates the destruction of all resources in the project.
#
# Usage: ./terraform/scripts/deletion_manager.sh [OPTIONS]
#
# ## Global Parameters
#   --project                    GCP Project ID (Required).
#   --region                     GCP Region (Default: us-central1).
#
# ## Gemini Enterprise Parameters
#   --delete-ge-app              Set to "true" to delete a Gemini Enterprise App.
#   (Note: GE_LOCATION and GE_APP_NAME_SUFFIX are shared between GE App and AI Agent)
#
# ## AI Agent Parameters
#   --delete-ai-agent            Set to "true" to delete AI Agent resources.
#   --ge-location                Location for the Vertex AI Agent Engine.
#   --agent-engine-location      Location for the Agent Engine Data Store.
#   --agent-display-name         The display name of the Agent.
#   --ge-app-name-suffix         The name suffix of the Gemini Enterprise App.
#   --ge-auth-id-secret-names    Comma-separated list of Auth Secret Names to delete.
#
# ## MCP Servers Parameters
#   --delete-mcp-servers         Set to "true" to delete MCP servers.
#   --mcp-servers-to-delete      Comma-separated list of MCP servers (e.g., "gcs,bq").
#
# ## Pipelines Parameters
#   --delete-ekb-pipeline        Set to "true" to delete the EKB pipeline.
#
# ## Shared Resources Parameters
#   --delete-shared-resources    Set to "true" to delete shared resources.
#   --shared-secrets-to-delete   Comma-separated list of shared secrets to delete.
#
# ## CICD Trigger Parameters (Bootstrap)
#   --delete-bootstrap           Set to "true" to delete Cloud Build triggers & SA.
#   --sa-name                    The base name of the Terraform service account.
#   --trigger-bases              Comma-separated list of the trigger bases.
# -----------------------------------------------------------------------------

# --- Global Configuration ---
PROJECT_ID=""
REGION=""
SA_NAME="terraform-sa-gemini-project"
# --- Shared GE App & AI Agent Parameters ---
GE_LOCATION=""
GE_APP_NAME_SUFFIX="osiris-app"

# --- Gemini Enterprise Parameters ---
DELETE_GE_APP="false"

# --- AI Agent Parameters ---
DELETE_AI_AGENT="false"
AGENT_ENGINE_LOCATION=""
AGENT_DISPLAY_NAME=""
GE_AUTH_ID_SECRET_NAMES="GEMINI_GOOGLE_AUTH_ID,GEMINI_MICROSOFT_AUTH_ID"

# --- MCP Servers Parameters ---
DELETE_MCP_SERVERS="false"
MCP_SERVERS_TO_DELETE="all"

# --- Pipelines Parameters ---
DELETE_EKB_PIPELINE="false"

# --- Shared Resources Parameters ---
DELETE_SHARED_RESOURCES="false"
SHARED_SECRETS_TO_DELETE="GOOGLE_OAUTH_CLIENT_ID,GOOGLE_OAUTH_CLIENT_SECRET,MICROSOFT_OAUTH_CLIENT_ID,MICROSOFT_OAUTH_CLIENT_SECRET"

# --- CICD Trigger Parameters (Bootstrap) ---
DELETE_BOOTSTRAP="false"
TRIGGER_BASES_STR="ai-agent,bq-mcp-server,gcs-mcp-server,drive-mcp-server,calendar-mcp-server,ekb-pipeline,onedrive-mcp-server"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        # Global
        --project) PROJECT_ID="$2"; shift ;;
        --region) REGION="$2"; shift ;;
        # Shared GE App & AI Agent
        --ge-location) GE_LOCATION="$2"; shift ;;
        --ge-app-name-suffix) GE_APP_NAME_SUFFIX="$2"; shift ;;
        
        # Gemini Enterprise
        --delete-ge-app) DELETE_GE_APP="$2"; shift ;;
        
        # AI Agent
        --delete-ai-agent) DELETE_AI_AGENT="$2"; shift ;;
        --agent-engine-location) AGENT_ENGINE_LOCATION="$2"; shift ;;
        --agent-display-name) AGENT_DISPLAY_NAME="$2"; shift ;;
        --ge-auth-id-secret-names) GE_AUTH_ID_SECRET_NAMES="$2"; shift ;;
        
        # MCP Servers
        --delete-mcp-servers) DELETE_MCP_SERVERS="$2"; shift ;;
        --mcp-servers-to-delete) MCP_SERVERS_TO_DELETE="$2"; shift ;;
        
        # Pipelines
        --delete-ekb-pipeline) DELETE_EKB_PIPELINE="$2"; shift ;;
        
        # Shared Resources
        --delete-shared-resources) DELETE_SHARED_RESOURCES="$2"; shift ;;
        --shared-secrets-to-delete) SHARED_SECRETS_TO_DELETE="$2"; shift ;;
        
        # CICD Trigger (Bootstrap)
        --delete-bootstrap) DELETE_BOOTSTRAP="$2"; shift ;;
        --sa-name) SA_NAME="$2"; shift ;;
        --trigger-bases) TRIGGER_BASES_STR="$2"; shift ;;
        
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Validation
if [[ -z "$PROJECT_ID" ]] || [[ -z "$REGION" ]]; then
    echo "Error: --project and --region are required globally."
    exit 1
fi
if [[ "$DELETE_GE_APP" == "true" ]] || [[ "$DELETE_AI_AGENT" == "true" ]]; then
    if [ -z "$GE_LOCATION" ] || [ -z "$GE_APP_NAME_SUFFIX" ]; then
        echo "Error: Missing shared parameters for Gemini Enterprise / AI Agent deletion."
        echo "Both operations require: --ge-location, --ge-app-name-suffix"
        exit 1
    fi
fi

if [[ "$DELETE_AI_AGENT" == "true" ]]; then
    if [ -z "$AGENT_ENGINE_LOCATION" ] || [ -z "$AGENT_DISPLAY_NAME" ] || [ -z "$GE_AUTH_ID_SECRET_NAMES" ]; then
        echo "Error: --delete-ai-agent is true, but missing required parameters."
        echo "Required: --agent-engine-location, --agent-display-name, --ge-auth-id-secret-names"
        exit 1
    fi
fi

if [[ "$DELETE_MCP_SERVERS" == "true" ]]; then
    if [[ -z "$MCP_SERVERS_TO_DELETE" ]]; then
        echo "Error: --delete-mcp-servers is true, but --mcp-servers-to-delete is missing."
        exit 1
    fi
fi

if [[ "$DELETE_SHARED_RESOURCES" == "true" ]]; then
    if [[ -z "$SHARED_SECRETS_TO_DELETE" ]]; then
        echo "Error: --delete-shared-resources is true, but --shared-secrets-to-delete is missing."
        exit 1
    fi
fi

if [[ "$DELETE_BOOTSTRAP" == "true" ]]; then
    if [[ -z "$SA_NAME" ]] || [[ -z "$TRIGGER_BASES_STR" ]]; then
        echo "Error: --delete-bootstrap is true, but --sa-name or --trigger-bases is missing."
        exit 1
    fi
fi
# Pre-compute variables for summary and execution
if [[ "$DELETE_GE_APP" == "true" ]] || [[ "$DELETE_AI_AGENT" == "true" ]]; then
    GE_APP_ID="${PROJECT_ID}-${GE_LOCATION}-${GE_APP_NAME_SUFFIX}"
fi

# Summary
echo "================================================================="
echo "MASTER DELETION ORCHESTRATOR"
echo "================================================================="
echo "Target Project: $PROJECT_ID"
echo ""
echo "You have requested the following deletions:"
echo "GE App: $DELETE_GE_APP"
echo "AI Agent Resources: $DELETE_AI_AGENT"

if [[ "$DELETE_GE_APP" == "true" ]] || [[ "$DELETE_AI_AGENT" == "true" ]]; then
    echo "  [Shared Parameters]"
    echo "  - GE Location: $GE_LOCATION"
    echo "  - GE App ID: $GE_APP_ID"
fi

if [[ "$DELETE_AI_AGENT" == "true" ]]; then
    echo "  [AI Agent Parameters]"
    echo "  - Agent Engine Location: $AGENT_ENGINE_LOCATION"
    echo "  - Agent Display Name: $AGENT_DISPLAY_NAME"
    echo "  - Auth Secrets to Auto-Delete: $GE_AUTH_ID_SECRET_NAMES"
fi
echo "MCP Servers: $DELETE_MCP_SERVERS"
if [[ "$DELETE_MCP_SERVERS" == "true" ]]; then
    echo "  - Servers to Delete: $MCP_SERVERS_TO_DELETE"
fi
echo "EKB Pipeline: $DELETE_EKB_PIPELINE"
echo "Shared Resources: $DELETE_SHARED_RESOURCES"
if [[ "$DELETE_SHARED_RESOURCES" == "true" ]]; then
    echo "  - Secrets to Delete: $SHARED_SECRETS_TO_DELETE"
fi
echo "Bootstrap Cleanup: $DELETE_BOOTSTRAP"
if [[ "$DELETE_BOOTSTRAP" == "true" ]]; then
    echo "  - SA Name: $SA_NAME"
    echo "  - Trigger Bases: $TRIGGER_BASES_STR"
fi
echo "================================================================="
read -p "Are you absolutely sure you want to proceed with these deletions? (y/N): " confirm

if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "Deletion cancelled."
    exit 0
fi

# Global setup
STATE_BUCKET="${PROJECT_ID}-terraform-state"

# 1. AI Agent and GE App
if [[ "$DELETE_AI_AGENT" == "true" ]] || [[ "$DELETE_GE_APP" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 1: Delete AI Agent & GE App Resources"
    echo "-----------------------------------------------------------------"

    echo 'y' | bash "$REPO_ROOT/terraform/ai_agent_resources/scripts/delete_resources.sh" \
        --delete-ai-agent "$DELETE_AI_AGENT" \
        --delete-ge-app "$DELETE_GE_APP" \
        --project "$PROJECT_ID" \
        --ge-location "$GE_LOCATION" \
        --agent-engine-location "$AGENT_ENGINE_LOCATION" \
        --ge-app-id "$GE_APP_ID" \
        --agent-display-name "$AGENT_DISPLAY_NAME" \
        --ge-auth-id-secret-names "$GE_AUTH_ID_SECRET_NAMES"
else
    echo "Skipping AI Agent and GE App Resources deletion."
fi

# 2. MCP Servers
if [[ "$DELETE_MCP_SERVERS" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 2: Delete MCP Servers"
    echo "-----------------------------------------------------------------"
    echo 'y' | bash "$SCRIPT_DIR/delete_mcp_servers.sh" --project "$PROJECT_ID" --servers "$MCP_SERVERS_TO_DELETE" --region "$REGION"
else
    echo "Skipping MCP Servers deletion."
fi

# 3. EKB Pipeline
if [[ "$DELETE_EKB_PIPELINE" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 3: Delete EKB Pipeline Resources"
    echo "-----------------------------------------------------------------"
    EKB_DIR="$REPO_ROOT/terraform/ekb_pipeline_resources"
    if [ -d "$EKB_DIR" ]; then
        echo "Initializing EKB Pipeline stack..."
        terraform -chdir="$EKB_DIR" init -reconfigure \
            -backend-config="bucket=${STATE_BUCKET}" \
            -backend-config="prefix=terraform/state/ekb-pipeline-resources"

        echo "Destroying EKB Pipeline stack..."
        echo "  - Project ID: $PROJECT_ID"
        echo "  - Main Region: $REGION"
        terraform -chdir="$EKB_DIR" destroy -var="project_id=$PROJECT_ID" -var="main_region=$REGION" -auto-approve || echo "Warning: Failed to destroy EKB pipeline."
    else
        echo "Warning: Directory $EKB_DIR not found. Skipping."
    fi
else
    echo "Skipping EKB Pipeline Resources deletion."
fi

# 4. Shared Resources
if [[ "$DELETE_SHARED_RESOURCES" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 4: Delete Shared Resources"
    echo "-----------------------------------------------------------------"
    SHARED_DIR="$REPO_ROOT/terraform/shared_resources"
    if [ -d "$SHARED_DIR" ]; then
        echo "Initializing Shared Resources stack..."
        terraform -chdir="$SHARED_DIR" init -reconfigure \
            -backend-config="bucket=${STATE_BUCKET}" \
            -backend-config="prefix=terraform/state/shared-resources"

        echo "Destroying Shared Resources stack..."
        echo "  - Project ID: $PROJECT_ID"
        echo "  - Main Region: $REGION"
        terraform -chdir="$SHARED_DIR" destroy -var="project_id=$PROJECT_ID" -var="main_region=$REGION" -auto-approve || echo "Warning: Failed to destroy shared resources."
    else
        echo "Warning: Directory $SHARED_DIR not found. Skipping Terraform destroy."
    fi

    echo "Deleting Shared Secrets..."
    IFS=',' read -ra SECRET_ARRAY <<< "$SHARED_SECRETS_TO_DELETE"
    for SECRET in "${SECRET_ARRAY[@]}"; do
        if [ -n "$SECRET" ]; then
            echo "Deleting secret: $SECRET"
            gcloud secrets delete "$SECRET" --project "$PROJECT_ID" --quiet || echo "Warning: Failed to delete $SECRET or it doesn't exist."
        fi
    done
else
    echo "Skipping Shared Resources deletion."
fi

# 5. Bootstrap Cleanup
if [[ "$DELETE_BOOTSTRAP" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 5: Bootstrap Cleanup (Triggers & Service Account)"
    echo "-----------------------------------------------------------------"
    echo 'y' | bash "$SCRIPT_DIR/delete_bootstrap.sh" \
        --project "$PROJECT_ID" \
        --region "$REGION" \
        --sa-name "$SA_NAME" \
        --trigger-bases "$TRIGGER_BASES_STR"
else
    echo "Skipping Bootstrap Cleanup."
fi

echo "================================================================="
echo "ORCHESTRATION COMPLETE."
echo "================================================================="
