#!/bin/bash
# scripts/cicd_triggers_deletion.sh

set -euo pipefail

# ==============================================================================
# Script: cicd_triggers_deletion.sh
# Purpose:
#   This script is responsible for dynamically deleting Cloud Build triggers
#   (CI/CD pipelines) based on requested modular flags.
#
# Usage:
#   This script should NOT be executed directly. It is designed to be called by
#   deletion_manager.sh.
#
# Parameters:
#   --project                            - The GCP Project ID where triggers exist.
#   --region                             - The default GCP region for the project.
#   --delete-shared-resources-triggers   - "true" to delete triggers for shared resources.
#   --delete-mcp-server-triggers         - "true" to delete triggers for the MCP Servers.
#   --mcp-server-triggers-to-delete      - Comma-separated list of MCP servers to delete triggers for (e.g. "gcs,bq" or "all").
#   --delete-ekb-pipeline-triggers       - "true" to delete the trigger for the EKB pipeline.
#   --delete-ai-agent-triggers           - "true" to delete the trigger for the AI Agent.
# ==============================================================================

# --- Core Parameters ---
PROJECT_ID=""
REGION=""

# --- Trigger Deletion Flags ---
DELETE_SHARED_RESOURCES_TRIGGERS="false"
DELETE_MCP_SERVER_TRIGGERS="false"
MCP_SERVER_TRIGGERS_TO_DELETE="all"
DELETE_EKB_PIPELINE_TRIGGERS="false"

# --- AI Agent Parameters ---
DELETE_AI_AGENT_TRIGGERS="false"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --project) PROJECT_ID="$2"; shift ;;
        --region) REGION="$2"; shift ;;
        --delete-shared-resources-triggers) DELETE_SHARED_RESOURCES_TRIGGERS="$2"; shift ;;
        --delete-mcp-server-triggers) DELETE_MCP_SERVER_TRIGGERS="$2"; shift ;;
        --mcp-server-triggers-to-delete) MCP_SERVER_TRIGGERS_TO_DELETE="$2"; shift ;;
        --delete-ekb-pipeline-triggers) DELETE_EKB_PIPELINE_TRIGGERS="$2"; shift ;;
        --delete-ai-agent-triggers) DELETE_AI_AGENT_TRIGGERS="$2"; shift ;;
        *) ;; # Ignore unknown params
    esac
    shift
done

if [[ -z "$PROJECT_ID" ]]; then echo "Error: --project is required."; exit 1; fi
if [[ -z "$REGION" ]]; then echo "Error: --region is required."; exit 1; fi

echo "Deleting Cloud Build triggers in project: ${PROJECT_ID}"

trigger_exists() {
  local name="$1"
  gcloud builds triggers describe "$name" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --quiet >/dev/null 2>&1
}

delete_trigger() {
  local name="$1"
  if trigger_exists "$name"; then
    echo "Deleting trigger: ${name}"
    gcloud builds triggers delete "$name" \
      --project="$PROJECT_ID" \
      --region="$REGION" \
      --quiet
  else
    echo "Trigger not found, skipping: ${name}"
  fi
}

# --- AI Agent Triggers ---
if [[ "$DELETE_AI_AGENT_TRIGGERS" == "true" ]]; then
    delete_trigger "ai-agent-services-plan"
    delete_trigger "ai-agent-services-apply"
fi

# --- MCP Server Triggers ---
if [[ "$DELETE_MCP_SERVER_TRIGGERS" == "true" ]]; then
    SERVER_LIST=()
    if [[ "$MCP_SERVER_TRIGGERS_TO_DELETE" == "all" ]]; then
        # Find all directories matching *_mcp_server_resources
        for dir in "terraform/"*_mcp_server_resources; do
            if [ -d "$dir" ]; then
                base=$(basename "$dir")
                prefix="${base%_mcp_server_resources}"
                SERVER_LIST+=("$prefix")
            fi
        done
    else
        IFS=',' read -ra SERVER_LIST <<< "$MCP_SERVER_TRIGGERS_TO_DELETE"
    fi

    for SERVER_ENTRY in "${SERVER_LIST[@]}"; do
        if [[ "$SERVER_ENTRY" =~ ^([^=]+)=([^=]+)$ ]]; then
            SERVER_BASE="${BASH_REMATCH[1]}"
        else
            SERVER_BASE="$SERVER_ENTRY"
        fi
        
        # Replace underscores with hyphens for the trigger name
        SERVER_BASE_HYPHEN="${SERVER_BASE//_/-}"
        
        delete_trigger "${SERVER_BASE_HYPHEN}-mcp-server-services-plan"
        delete_trigger "${SERVER_BASE_HYPHEN}-mcp-server-services-apply"
    done
fi

# --- EKB Pipeline Triggers ---
if [[ "$DELETE_EKB_PIPELINE_TRIGGERS" == "true" ]]; then
    delete_trigger "ekb-pipeline-services-plan"
    delete_trigger "ekb-pipeline-services-apply"
fi
