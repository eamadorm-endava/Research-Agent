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
#   --region                     GCP Region (Default: europe-west2).
#
# ## Gemini Enterprise Parameters
#   --delete-ge-app              Set to "true" to delete a Gemini Enterprise App.
#   --ge-app-location            Location for the Gemini Enterprise App.
#   --ge-app-name-suffix         The name suffix of the Gemini Enterprise App.
#
# ## AI Agent Parameters
#   --unregister-ai-agent        Set to "true" to unregister the agent from GE and remove Auth IDs.
#   --delete-ai-agent            Set to "true" to delete the Vertex Reasoning Engine and TF resources.
#   --agent-engine-location      Location for the Agent Engine Data Store.
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
# ## CICD Trigger Parameters
#   --delete-cicd-triggers       Set to "true" to delete Cloud Build triggers.
#
# ## Bootstrap Parameters
#   --delete-bootstrap           Set to "true" to delete Bootstrap SA and IAM roles.
#   --sa-name                    The base name of the Terraform service account.
# -----------------------------------------------------------------------------

# --- Global Configuration ---
PROJECT_ID=""
REGION=""
SA_NAME="terraform-sa-gemini-project"

# --- Shared GE App & AI Agent Parameters ---
GE_APP_LOCATION=""
GE_APP_NAME_SUFFIX="osiris-app"

# --- AI Agent Parameters ---
UNREGISTER_AI_AGENT="false"
DELETE_AI_AGENT="false"
AGENT_ENGINE_LOCATION=""

# --- Gemini Enterprise App Parameters ---
DELETE_GE_APP="false"

# --- MCP Servers Parameters ---
DELETE_MCP_SERVERS="false"
MCP_SERVERS_TO_DELETE="all"

# --- Pipelines Parameters ---
DELETE_EKB_PIPELINE="false"

# --- Shared Resources Parameters ---
DELETE_SHARED_RESOURCES="false"
SHARED_SECRETS_TO_DELETE="GOOGLE_OAUTH_CLIENT_ID,GOOGLE_OAUTH_CLIENT_SECRET,MICROSOFT_OAUTH_CLIENT_ID,MICROSOFT_OAUTH_CLIENT_SECRET,ATLASSIAN_CREDENTIALS"

# --- CICD Trigger Parameters ---
DELETE_CICD_TRIGGERS="false"

# --- Bootstrap Parameters ---
DELETE_BOOTSTRAP="false"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        # Global
        --project) PROJECT_ID="$2"; shift ;;
        --region) REGION="$2"; shift ;;
        
        # Shared GE App & AI Agent
        --ge-app-location) GE_APP_LOCATION="$2"; shift ;;
        --ge-app-name-suffix) GE_APP_NAME_SUFFIX="$2"; shift ;;
        
        # AI Agent
        --unregister-ai-agent) UNREGISTER_AI_AGENT="$2"; shift ;;
        --delete-ai-agent) DELETE_AI_AGENT="$2"; shift ;;
        --agent-engine-location) AGENT_ENGINE_LOCATION="$2"; shift ;;

        # Gemini Enterprise
        --delete-ge-app) DELETE_GE_APP="$2"; shift ;;
        
        # MCP Servers
        --delete-mcp-servers) DELETE_MCP_SERVERS="$2"; shift ;;
        --mcp-servers-to-delete) MCP_SERVERS_TO_DELETE="$2"; shift ;;
        
        # Pipelines
        --delete-ekb-pipeline) DELETE_EKB_PIPELINE="$2"; shift ;;
        
        # Shared Resources
        --delete-shared-resources) DELETE_SHARED_RESOURCES="$2"; shift ;;
        --shared-secrets-to-delete) SHARED_SECRETS_TO_DELETE="$2"; shift ;;
        
        # CICD Triggers
        --delete-cicd-triggers) DELETE_CICD_TRIGGERS="$2"; shift ;;

        # Bootstrap
        --delete-bootstrap) DELETE_BOOTSTRAP="$2"; shift ;;
        --sa-name) SA_NAME="$2"; shift ;;
        
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Validation
if [[ -z "$PROJECT_ID" ]] || [[ -z "$REGION" ]]; then
    echo "Error: --project and --region are required globally."
    exit 1
fi

if [[ "$DELETE_BOOTSTRAP" == "true" ]]; then
    DELETE_CICD_TRIGGERS="true"
fi

if [[ "$DELETE_AI_AGENT" == "true" ]]; then
    UNREGISTER_AI_AGENT="true"
fi

DEL_AI_TRIGGERS="$DELETE_AI_AGENT"
DEL_MCP_TRIGGERS="$DELETE_MCP_SERVERS"
MCP_DEL_TARGET="$MCP_SERVERS_TO_DELETE"
DEL_EKB_TRIGGERS="$DELETE_EKB_PIPELINE"

if [[ "$DELETE_CICD_TRIGGERS" == "true" ]]; then
    DEL_AI_TRIGGERS="true"
    DEL_MCP_TRIGGERS="true"
    MCP_DEL_TARGET="all"
    DEL_EKB_TRIGGERS="true"
fi

if [[ "$UNREGISTER_AI_AGENT" == "true" ]] || [[ "$DELETE_GE_APP" == "true" ]]; then
    if [ -z "$GE_APP_LOCATION" ] || [ -z "$GE_APP_NAME_SUFFIX" ]; then
        echo "Error: Missing shared parameters for Gemini Enterprise / AI Agent unregistration."
        echo "Both operations require: --ge-app-location, --ge-app-name-suffix"
        exit 1
    fi
fi

if [[ "$DELETE_AI_AGENT" == "true" ]]; then
    if [ -z "$AGENT_ENGINE_LOCATION" ]; then
        echo "Error: --delete-ai-agent is true, but missing required parameters."
        echo "Required: --agent-engine-location"
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
    if [[ -z "$SA_NAME" ]]; then
        echo "Error: --delete-bootstrap is true, but --sa-name is missing."
        exit 1
    fi
fi

# Pre-compute variables for summary and execution
if [[ "$DELETE_GE_APP" == "true" ]] || [[ "$UNREGISTER_AI_AGENT" == "true" ]]; then
    GE_APP_ID="${PROJECT_ID}-${GE_APP_LOCATION}-${GE_APP_NAME_SUFFIX}"
fi

if [[ "$UNREGISTER_AI_AGENT" == "true" ]] || [[ "$DELETE_AI_AGENT" == "true" ]]; then
    YAML_FILE="$REPO_ROOT/terraform/ai_agent_resources/ai-agent-services-cloud-build-cd.yaml"
    AGENT_DISPLAY_NAME=$(grep -E '^[[:space:]]+_AGENT_DISPLAY_NAME:' "$YAML_FILE" | sed -E 's/.*_AGENT_DISPLAY_NAME:[[:space:]]*"([^"]+)".*/\1/')
    GEMINI_GOOGLE_AUTH_ID=$(grep -E '^[[:space:]]+_GEMINI_GOOGLE_AUTH_ID:' "$YAML_FILE" | sed -E 's/.*_GEMINI_GOOGLE_AUTH_ID:[[:space:]]*"([^"]+)".*/\1/')
    GEMINI_MICROSOFT_AUTH_ID=$(grep -E '^[[:space:]]+_GEMINI_MICROSOFT_AUTH_ID:' "$YAML_FILE" | sed -E 's/.*_GEMINI_MICROSOFT_AUTH_ID:[[:space:]]*"([^"]+)".*/\1/')
    GE_AUTH_IDS="${GEMINI_GOOGLE_AUTH_ID},${GEMINI_MICROSOFT_AUTH_ID}"
fi

# Summary
echo "================================================================="
echo "MASTER DELETION ORCHESTRATOR"
echo "================================================================="
echo "Target Project: $PROJECT_ID"
echo "Default Region: $REGION"
echo ""
echo "You have requested the following deletions:"

echo "Step 1: Unregister Agent & Auth IDs: $UNREGISTER_AI_AGENT"
if [[ "$UNREGISTER_AI_AGENT" == "true" ]]; then
    echo "  - GE App ID: $GE_APP_ID"
    echo "  - Agent Display Name: $AGENT_DISPLAY_NAME"
    echo "  - Auth IDs to Delete: $GE_AUTH_IDS"
fi

echo "Step 2: Delete Vertex Agent & TF Resources: $DELETE_AI_AGENT"
if [[ "$DELETE_AI_AGENT" == "true" ]]; then
    echo "  - Agent Engine Location: $AGENT_ENGINE_LOCATION"
    echo "  - Agent Display Name: $AGENT_DISPLAY_NAME"
fi

echo "Step 3: Delete Gemini Enterprise App: $DELETE_GE_APP"
if [[ "$DELETE_GE_APP" == "true" ]]; then
    echo "  - GE App Location: $GE_APP_LOCATION"
    echo "  - GE App ID: $GE_APP_ID"
fi

echo "Step 4: MCP Servers: $DELETE_MCP_SERVERS"
if [[ "$DELETE_MCP_SERVERS" == "true" ]]; then
    echo "  - Servers to Delete: $MCP_SERVERS_TO_DELETE"
fi

echo "Step 5: EKB Pipeline: $DELETE_EKB_PIPELINE"

echo "Step 6: Shared Resources: $DELETE_SHARED_RESOURCES"
if [[ "$DELETE_SHARED_RESOURCES" == "true" ]]; then
    echo "  - Secrets to Delete: $SHARED_SECRETS_TO_DELETE"
fi

if [[ "$DELETE_CICD_TRIGGERS" == "true" ]] || [[ "$DEL_AI_TRIGGERS" == "true" ]] || [[ "$DEL_MCP_TRIGGERS" == "true" ]] || [[ "$DEL_EKB_TRIGGERS" == "true" ]] || [[ "$DELETE_SHARED_RESOURCES" == "true" ]]; then
    echo "Step 7: CI/CD Triggers: true (Modular Cleanup)"
    if [[ "$DELETE_CICD_TRIGGERS" == "true" ]]; then
        echo "  - Wiping ALL CI/CD Triggers"
    else
        [[ "$DEL_AI_TRIGGERS" == "true" ]] && echo "  - AI Agent Triggers"
        [[ "$DEL_MCP_TRIGGERS" == "true" ]] && echo "  - MCP Server Triggers ($MCP_DEL_TARGET)"
        [[ "$DEL_EKB_TRIGGERS" == "true" ]] && echo "  - EKB Pipeline Triggers"
        [[ "$DELETE_SHARED_RESOURCES" == "true" ]] && echo "  - Shared Resources Triggers"
    fi
else
    echo "Step 7: CI/CD Triggers: false"
fi

echo "Step 8: Bootstrap Cleanup: $DELETE_BOOTSTRAP"
if [[ "$DELETE_BOOTSTRAP" == "true" ]]; then
    echo "  - SA Name: $SA_NAME"
fi

echo "================================================================="
read -p "Are you absolutely sure you want to proceed with these deletions? (y/N): " confirm

if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "Deletion cancelled."
    exit 0
fi

# Global setup
STATE_BUCKET="${PROJECT_ID}-terraform-state"

# -----------------------------------------------------------------
# 1. Unregister Agent & Auth IDs
# -----------------------------------------------------------------
if [[ "$UNREGISTER_AI_AGENT" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 1: Unregister Agent & Delete Auth IDs"
    echo "-----------------------------------------------------------------"
    
    echo "Unregistering Agent..."
    bash "$REPO_ROOT/terraform/ai_agent_resources/scripts/ge_agent_manager.sh" unregister-agent \
        --project "$PROJECT_ID" \
        --app-id "$GE_APP_ID" \
        --agent-display-name "$AGENT_DISPLAY_NAME" \
        --ge-location "$GE_APP_LOCATION"

    echo "Deleting Auth IDs..."
    bash "$REPO_ROOT/terraform/ai_agent_resources/scripts/ge_agent_manager.sh" delete-auth-ids \
        --project "$PROJECT_ID" \
        --auth-ids "$GE_AUTH_IDS" \
        --ge-location "$GE_APP_LOCATION"
else
    echo "Skipping Step 1: Unregister Agent & Auth IDs."
fi

# -----------------------------------------------------------------
# 2. Delete Vertex Agent & AI Agent TF Resources
# -----------------------------------------------------------------
if [[ "$DELETE_AI_AGENT" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 2: Delete Vertex Agent & TF Resources"
    echo "-----------------------------------------------------------------"
    
    echo "Deleting Reasoning Engine in Vertex AI..."
    uv run --group ai-agent python "$REPO_ROOT/terraform/ai_agent_resources/scripts/delete_agent_engine.py" \
        --project "$PROJECT_ID" \
        --location "$AGENT_ENGINE_LOCATION" \
        --display-name "$AGENT_DISPLAY_NAME" \
        --force

    echo "Executing terraform destroy for AI Agent Resources..."
    pushd "$REPO_ROOT/terraform/ai_agent_resources" > /dev/null
    terraform init -reconfigure \
        -backend-config="bucket=${STATE_BUCKET}" \
        -backend-config="prefix=terraform/state/ai-agent-resources"
    terraform destroy -auto-approve -var="project_id=$PROJECT_ID" -var="main_region=$AGENT_ENGINE_LOCATION"
    popd > /dev/null
else
    echo "Skipping Step 2: Delete Vertex Agent & TF Resources."
fi

# -----------------------------------------------------------------
# 3. Delete Gemini Enterprise App
# -----------------------------------------------------------------
if [[ "$DELETE_GE_APP" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 3: Delete Gemini Enterprise App"
    echo "-----------------------------------------------------------------"
    
    bash "$REPO_ROOT/terraform/ai_agent_resources/scripts/ge_agent_manager.sh" delete-ge-app \
        --project "$PROJECT_ID" \
        --ge-location "$GE_APP_LOCATION" \
        --ge-app-id "$GE_APP_ID"
else
    echo "Skipping Step 3: Gemini Enterprise App deletion."
fi

# -----------------------------------------------------------------
# 4. Delete MCP Servers
# -----------------------------------------------------------------
if [[ "$DELETE_MCP_SERVERS" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 4: Delete MCP Servers"
    echo "-----------------------------------------------------------------"
    SERVER_LIST=()
    if [[ "$MCP_SERVERS_TO_DELETE" == "all" ]]; then
        for dir in "$REPO_ROOT/terraform/"*_mcp_server_resources; do
            if [ -d "$dir" ]; then
                base=$(basename "$dir")
                prefix="${base%_mcp_server_resources}"
                SERVER_LIST+=("$prefix")
            fi
        done
    else
        IFS=',' read -ra SERVER_LIST <<< "$MCP_SERVERS_TO_DELETE"
    fi

    for SERVER_ENTRY in "${SERVER_LIST[@]}"; do
        if [[ "$SERVER_ENTRY" =~ ^([^=]+)=([^=]+)$ ]]; then
            SERVER_BASE="${BASH_REMATCH[1]}"
            SERVER_REGION="${BASH_REMATCH[2]}"
        else
            SERVER_BASE="$SERVER_ENTRY"
            SERVER_REGION="$REGION"
        fi
        
        STACK_NAME="${SERVER_BASE}_mcp_server_resources"
        STACK_DIR="$REPO_ROOT/terraform/$STACK_NAME"
        
        if [ ! -d "$STACK_DIR" ]; then
            echo "Warning: Directory $STACK_DIR not found. Skipping MCP server '$SERVER_BASE'."
            continue
        fi
        
        SERVER_BASE_HYPHEN="${SERVER_BASE//_/-}"
        STATE_PREFIX="terraform/state/${SERVER_BASE_HYPHEN}-mcp-server-resources"
        
        echo "---------------------------------------"
        echo "Destroying MCP Terraform stack: $STACK_NAME (Region: $SERVER_REGION)"
        echo "State prefix: $STATE_PREFIX"

        terraform -chdir="$STACK_DIR" init -reconfigure \
            -backend-config="bucket=${STATE_BUCKET}" \
            -backend-config="prefix=${STATE_PREFIX}"

        echo "Resources currently tracked in state:"
        terraform -chdir="$STACK_DIR" state list >/dev/null 2>&1 && terraform -chdir="$STACK_DIR" state list || true

        echo "Destroying $STACK_NAME..."
        export TF_VAR_landing_zone_bucket="${PROJECT_ID}-ai-agent-landing-zone"
        export TF_VAR_kb_ingestion_bucket="${PROJECT_ID}-kb-landing-zone"
        
        terraform -chdir="$STACK_DIR" destroy -var="project_id=$PROJECT_ID" -var="main_region=$SERVER_REGION" -auto-approve || echo "Warning: Failed to destroy $STACK_NAME. Skipping."
    done
else
    echo "Skipping Step 4: MCP Servers deletion."
fi

# -----------------------------------------------------------------
# 5. Delete EKB Pipeline
# -----------------------------------------------------------------
if [[ "$DELETE_EKB_PIPELINE" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 5: Delete EKB Pipeline Resources"
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
    echo "Skipping Step 5: EKB Pipeline Resources deletion."
fi

# -----------------------------------------------------------------
# 6. Delete Shared Resources
# -----------------------------------------------------------------
if [[ "$DELETE_SHARED_RESOURCES" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 6: Delete Shared Resources"
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
    echo "Skipping Step 6: Shared Resources deletion."
fi

# -----------------------------------------------------------------
# 7. Delete CI/CD Triggers
# -----------------------------------------------------------------
if [[ "$DELETE_CICD_TRIGGERS" == "true" ]] || [[ "$DEL_AI_TRIGGERS" == "true" ]] || [[ "$DEL_MCP_TRIGGERS" == "true" ]] || [[ "$DEL_EKB_TRIGGERS" == "true" ]] || [[ "$DELETE_SHARED_RESOURCES" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 7: Delete CI/CD Triggers"
    echo "-----------------------------------------------------------------"
    # If global wipe is requested, force all modular flags to true
    if [[ "$DELETE_CICD_TRIGGERS" == "true" ]]; then
        DEL_SHARED_TRIGGERS="true"
        DEL_MCP_TRIGGERS_FLAG="true"
        MCP_DEL_TARGET="all"
        DEL_EKB_TRIGGERS_FLAG="true"
        DEL_AI_TRIGGERS_FLAG="true"
    else
        DEL_SHARED_TRIGGERS="$DELETE_SHARED_RESOURCES"
        DEL_MCP_TRIGGERS_FLAG="$DEL_MCP_TRIGGERS"
        DEL_EKB_TRIGGERS_FLAG="$DEL_EKB_TRIGGERS"
        DEL_AI_TRIGGERS_FLAG="$DEL_AI_TRIGGERS"
    fi

    bash "$SCRIPT_DIR/cicd_triggers_deletion.sh" \
        --project "$PROJECT_ID" \
        --region "$REGION" \
        --delete-shared-resources-triggers "$DEL_SHARED_TRIGGERS" \
        --delete-mcp-server-triggers "$DEL_MCP_TRIGGERS_FLAG" \
        --mcp-server-triggers-to-delete "$MCP_DEL_TARGET" \
        --delete-ekb-pipeline-triggers "$DEL_EKB_TRIGGERS_FLAG" \
        --delete-ai-agent-triggers "$DEL_AI_TRIGGERS_FLAG"
else
    echo "Skipping Step 7: CI/CD Triggers cleanup."
fi

# -----------------------------------------------------------------
# 8. Delete Bootstrap
# -----------------------------------------------------------------
if [[ "$DELETE_BOOTSTRAP" == "true" ]]; then
    echo "-----------------------------------------------------------------"
    echo "STEP 8: Bootstrap Cleanup (Service Account & State Bucket)"
    echo "-----------------------------------------------------------------"
    echo 'y' | bash "$SCRIPT_DIR/delete_bootstrap.sh" \
        --project "$PROJECT_ID" \
        --sa-name "$SA_NAME"
else
    echo "Skipping Step 8: Bootstrap Cleanup."
fi

echo "================================================================="
echo "ORCHESTRATION COMPLETE."
echo "================================================================="
