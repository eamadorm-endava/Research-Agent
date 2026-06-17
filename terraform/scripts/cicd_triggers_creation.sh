#!/bin/bash

set -euo pipefail

# ==============================================================================
# Script: cicd_triggers_creation.sh
# Purpose:
#   This script is responsible for creating all the necessary Cloud Build triggers
#   (CI/CD pipelines) for the AI Agent, MCP Servers, and the EKB pipeline.
#   It dynamically creates only the triggers requested via parameters, and prevents
#   duplication if they already exist.
#
# Usage:
#   This script should NOT be executed directly. It is designed to be called by
#   creation_manager.sh, which parses user intentions and injects all required
#   environment variables and parameters.
#
# Required Environment Variables:
#   PROJECT_ID             - The GCP Project ID where triggers will be created.
#   SA_NAME                - The name of the Service Account (used for trigger auth).
#   SA_EMAIL               - The full email of the Service Account.
#   GITHUB_CONNECTION_NAME - The Cloud Build GitHub Connection name.
#   REPOSITORY_SLUG        - The GitHub Repository Slug.
#                            This is the exact identifier format required by Cloud Build when linking
#                            a 2nd Gen repository connection, strictly formatted as "owner-repo".
#
# Parameters:
#   --region                 - The default GCP region for the project.
#   --deploy-mcp-servers     - "true" to create triggers for the MCP Servers.
#   --mcp-servers-to-deploy  - Comma-separated list of MCP servers to create triggers for.
#   --deploy-ekb-pipeline    - "true" to create the trigger for the EKB pipeline.
#   --deploy-ai-agent        - "true" to create the trigger for the AI Agent.
#   --force-recreate         - "true" to delete and recreate triggers if they exist.
#
#   [AI Agent Parameters - Required if --deploy-ai-agent is true]
#   --ge-app-location        - The location of the Gemini Enterprise App.
#   --ge-app-name-suffix     - The name suffix of the Gemini Enterprise App.
#   --bq-url                 - The BigQuery MCP server Cloud Run URL.
#   --gcs-url                - The GCS MCP server Cloud Run URL.
#   --drive-url              - The Google Drive MCP server Cloud Run URL.
#   --calendar-url           - The Google Calendar MCP server Cloud Run URL.
#   --onedrive-url           - The OneDrive MCP server Cloud Run URL.
#   --ekb-pipeline-url       - The EKB Pipeline Cloud Run URL.
# ==============================================================================

# --- Parameters ---
REGION=""
DEPLOY_MCP_SERVERS="false"
MCP_SERVERS_TO_DEPLOY="all"
DEPLOY_EKB_PIPELINE="false"

# --- AI Agent Parameters ---
DEPLOY_AI_AGENT="false"
GE_APP_LOCATION=""
GE_APP_NAME_SUFFIX=""
BQ_URL=""
GCS_URL=""
DRIVE_URL=""
CALENDAR_URL=""
ONEDRIVE_URL=""
EKB_URL=""

# --- Optional / Overridable Variables ---
PR_TARGET_BRANCH_REGEX="${PR_TARGET_BRANCH_REGEX:-^main$}"
PUSH_BRANCH_REGEX="${PUSH_BRANCH_REGEX:-^main$}"
FORCE_RECREATE="${FORCE_RECREATE:-false}"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --region) REGION="$2"; shift ;;
        --deploy-mcp-servers) DEPLOY_MCP_SERVERS="$2"; shift ;;
        --mcp-servers-to-deploy) MCP_SERVERS_TO_DEPLOY="$2"; shift ;;
        --deploy-ekb-pipeline) DEPLOY_EKB_PIPELINE="$2"; shift ;;
        --force-recreate) FORCE_RECREATE="$2"; shift ;;
        
        # AI Agent Specific
        --deploy-ai-agent) DEPLOY_AI_AGENT="$2"; shift ;;
        --ge-app-location) GE_APP_LOCATION="$2"; shift ;;
        --ge-app-name-suffix) GE_APP_NAME_SUFFIX="$2"; shift ;;
        --bq-url) BQ_URL="$2"; shift ;;
        --gcs-url) GCS_URL="$2"; shift ;;
        --drive-url) DRIVE_URL="$2"; shift ;;
        --calendar-url) CALENDAR_URL="$2"; shift ;;
        --onedrive-url) ONEDRIVE_URL="$2"; shift ;;
        --ekb-pipeline-url) EKB_URL="$2"; shift ;;
        *) ;; # Ignore unknown params
    esac
    shift
done

if [[ -z "$REGION" ]]; then
    echo "Error: --region is required."
    exit 1
fi

# Require essential variables from the environment (e.g. from bootstrap.sh)
if [[ -z "${PROJECT_ID:-}" ]]; then echo "Error: PROJECT_ID environment variable is missing."; exit 1; fi
if [[ -z "${SA_NAME:-}" ]]; then echo "Error: SA_NAME environment variable is missing."; exit 1; fi
if [[ -z "${SA_EMAIL:-}" ]]; then echo "Error: SA_EMAIL environment variable is missing."; exit 1; fi
if [[ -z "${GITHUB_CONNECTION_NAME:-}" ]]; then echo "Error: GITHUB_CONNECTION_NAME environment variable is missing."; exit 1; fi
if [[ -z "${REPOSITORY_SLUG:-}" ]]; then echo "Error: REPOSITORY_SLUG environment variable is missing."; exit 1; fi

if [[ "$DEPLOY_AI_AGENT" == "true" ]]; then
    if [[ -z "$GE_APP_LOCATION" ]] || [[ -z "$GE_APP_NAME_SUFFIX" ]] || [[ -z "$BQ_URL" ]] || [[ -z "$GCS_URL" ]] || [[ -z "$DRIVE_URL" ]] || [[ -z "$CALENDAR_URL" ]] || [[ -z "$ONEDRIVE_URL" ]] || [[ -z "$EKB_URL" ]]; then
        echo "Error: --deploy-ai-agent is true, but missing required AI Agent parameters."
        echo "Required: --ge-app-location, --ge-app-name-suffix, --bq-url, --gcs-url, --drive-url, --calendar-url, --onedrive-url, --ekb-pipeline-url"
        exit 1
    fi
fi

PROJECT_NUMBER="${PROJECT_NUMBER:-$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')}"
REPO_PATH="projects/${PROJECT_NUMBER}/locations/${REGION}/connections/${GITHUB_CONNECTION_NAME}/repositories/${REPOSITORY_SLUG}"

echo "Creating Cloud Build triggers in project: ${PROJECT_ID}"
echo "Using repository connection path: ${REPO_PATH}"
echo "Force recreate existing triggers: ${FORCE_RECREATE}"

trigger_exists() {
  local name="$1"
  gcloud builds triggers describe "$name" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --quiet >/dev/null 2>&1
}

delete_trigger() {
  local name="$1"
  gcloud builds triggers delete "$name" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --quiet
}

create_trigger() {
  local name="$1"
  local type="$2"
  local dir="$3"
  local config="$4"
  local extra_dir="$5"
  local extra_substitutions="${6:-}"

  local included_files="${dir}/**"
  if [[ -n "$extra_dir" ]]; then
    included_files="${included_files},${extra_dir}"
  fi
  
  local subs="_SA_NAME=$SA_NAME"
  if [[ -n "$extra_substitutions" ]]; then
    subs="${subs},${extra_substitutions}"
  fi

  if trigger_exists "$name"; then
    if [[ "$FORCE_RECREATE" == "true" ]]; then
      echo "Trigger exists and will be recreated: ${name}"
      delete_trigger "$name"
    else
      echo "Trigger already exists, skipping: ${name}"
      return
    fi
  fi

  if [[ "$type" == "pr" ]]; then
    echo "Creating PR trigger: ${name}"
    gcloud alpha builds triggers create github \
      --name="$name" \
      --project="$PROJECT_ID" \
      --region="$REGION" \
      --repository="$REPO_PATH" \
      --pull-request-pattern="$PR_TARGET_BRANCH_REGEX" \
      --build-config="$config" \
      --included-files="$included_files" \
      --service-account="projects/$PROJECT_ID/serviceAccounts/$SA_EMAIL" \
      --substitutions="$subs"
  else
    echo "Creating push trigger: ${name}"
    gcloud alpha builds triggers create github \
      --name="$name" \
      --project="$PROJECT_ID" \
      --region="$REGION" \
      --repository="$REPO_PATH" \
      --branch-pattern="$PUSH_BRANCH_REGEX" \
      --build-config="$config" \
      --included-files="$included_files" \
      --service-account="projects/$PROJECT_ID/serviceAccounts/$SA_EMAIL" \
      --substitutions="$subs"
  fi
}

# --- AI Agent Triggers ---
if [[ "$DEPLOY_AI_AGENT" == "true" ]]; then
    AI_AGENT_SUBS="_GE_REGION=$GE_APP_LOCATION,_GE_APP_NAME_SUFFIX=$GE_APP_NAME_SUFFIX,_BIGQUERY_URL=$BQ_URL,_GCS_URL=$GCS_URL,_DRIVE_URL=$DRIVE_URL,_CALENDAR_URL=$CALENDAR_URL,_ONEDRIVE_URL=$ONEDRIVE_URL,_EKB_PIPELINE_URL=$EKB_URL"

    # CI (Plan) on Pull Request
    create_trigger "ai-agent-services-plan" "pr" "terraform/ai_agent_resources" "terraform/ai_agent_resources/ai-agent-services-cloud-build-ci.yaml" "agent/**" "$AI_AGENT_SUBS"
    # CD (Apply) on Push/Merge
    create_trigger "ai-agent-services-apply" "push" "terraform/ai_agent_resources" "terraform/ai_agent_resources/ai-agent-services-cloud-build-cd.yaml" "agent/**" "$AI_AGENT_SUBS"
fi

# --- MCP Server Triggers ---
if [[ "$DEPLOY_MCP_SERVERS" == "true" ]]; then
    SERVER_LIST=()
    if [[ "$MCP_SERVERS_TO_DEPLOY" == "all" ]]; then
        # Find all directories matching *_mcp_server_resources
        for dir in "terraform/"*_mcp_server_resources; do
            if [ -d "$dir" ]; then
                base=$(basename "$dir")
                prefix="${base%_mcp_server_resources}"
                SERVER_LIST+=("$prefix")
            fi
        done
    else
        IFS=',' read -ra SERVER_LIST <<< "$MCP_SERVERS_TO_DEPLOY"
    fi

    for SERVER_ENTRY in "${SERVER_LIST[@]}"; do
        if [[ "$SERVER_ENTRY" =~ ^([^=]+)=([^=]+)$ ]]; then
            SERVER_BASE="${BASH_REMATCH[1]}"
        else
            SERVER_BASE="$SERVER_ENTRY"
        fi
        
        STACK_NAME="${SERVER_BASE}_mcp_server_resources"
        STACK_DIR="terraform/$STACK_NAME"
        
        if [ ! -d "$STACK_DIR" ]; then
            echo "Warning: Directory $STACK_DIR not found. Skipping trigger creation for '$SERVER_BASE'."
            continue
        fi

        # Dynamically determine the source directory for included_files by parsing the CI yaml.
        # Reason: This intelligently bridges the naming gap between the Terraform module folder 
        # (e.g., "bq") and the underlying Python package folder (e.g., "mcp_servers/big_query")
        # without needing to hardcode the mapping.
        CI_YAML="${STACK_DIR}/mcp-server-services-cloud-build-ci.yaml"
        CD_YAML="${STACK_DIR}/mcp-server-services-cloud-build-cd.yaml"
        
        if [ -f "$CI_YAML" ]; then
            MCP_SOURCE_DIR=$(grep -oE "mcp_servers/[^/]+" "$CI_YAML" | head -n 1)
            if [ -n "$MCP_SOURCE_DIR" ]; then
                INCLUDED_PATH="${MCP_SOURCE_DIR}/**"
                
                # Replace underscores with hyphens for the trigger name (e.g. google_drive -> google-drive)
                SERVER_BASE_HYPHEN="${SERVER_BASE//_/-}"
                
                create_trigger "${SERVER_BASE_HYPHEN}-mcp-server-services-plan" "pr" "$STACK_DIR" "$CI_YAML" "$INCLUDED_PATH"
                create_trigger "${SERVER_BASE_HYPHEN}-mcp-server-services-apply" "push" "$STACK_DIR" "$CD_YAML" "$INCLUDED_PATH"
            else
                echo "Warning: Could not parse source directory from $CI_YAML. Skipping $SERVER_BASE."
            fi
        else
             echo "Warning: $CI_YAML not found. Skipping $SERVER_BASE."
        fi
    done
fi

# --- EKB Pipeline Triggers ---
if [[ "$DEPLOY_EKB_PIPELINE" == "true" ]]; then
    create_trigger "ekb-pipeline-services-plan" "pr" "terraform/ekb_pipeline_resources" "terraform/ekb_pipeline_resources/ekb-pipeline-services-cloud-build-ci.yaml" "pipelines/enterprise_knowledge_base/**"
    create_trigger "ekb-pipeline-services-apply" "push" "terraform/ekb_pipeline_resources" "terraform/ekb_pipeline_resources/ekb-pipeline-services-cloud-build-cd.yaml" "pipelines/enterprise_knowledge_base/**"
fi

echo "Done. Requested triggers processed."
