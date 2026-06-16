#!/bin/bash
# scripts/delete_mcp_servers.sh

# Exit on error and fail on unset variables or failed pipeline commands.
set -euo pipefail

# -----------------------------------------------------------------------------
# MCP Server Terraform Deletion Script
# -----------------------------------------------------------------------------
# This script destroys only the MCP server Terraform stacks:
#   - GCS MCP server
#   - BigQuery MCP server
#   - Google Drive MCP server
#   - Google Calendar MCP server
#   - OneDrive MCP server
#
# It intentionally does not destroy shared resources, the AI Agent, the EKB
# pipeline, the Terraform state bucket, or the Terraform service account.
#
# Run this script from the repository root:
#   ./terraform/scripts/delete_mcp_servers.sh --project <PROJECT_ID> --region <REGION>
#
# Required parameters:
#   --project            GCP Project ID
#   --region             Default GCP Region for the MCP servers
#
# Optional parameters:
#   --servers            Comma-separated list of servers to delete (e.g., "onedrive,google_calendar=europe-west1") or "all".
#                        If a location is appended with '=', it overrides the default region for that specific server.
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- Configuration ---
PROJECT_ID=""
REGION=""
SERVERS_TO_DELETE=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --project) PROJECT_ID="$2"; shift ;;
        --servers) SERVERS_TO_DELETE="$2"; shift ;;
        --region) REGION="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

if [[ -z "$PROJECT_ID" ]] || [[ -z "$REGION" ]] || [[ -z "$SERVERS_TO_DELETE" ]]; then
    echo "Error: --project, --region, and --servers parameters are required."
    exit 1
fi

STATE_BUCKET="${STATE_BUCKET:-${PROJECT_ID}-terraform-state}"

# We dynamically construct the Terraform stack and state paths based on the provided prefixes.

confirm_destroy() {
    echo "This will destroy MCP server Terraform resources in project: $PROJECT_ID"
    echo "Parameters:"
    echo "  - Region: $REGION"
    echo "  - Servers: $SERVERS_TO_DELETE"
    echo "Terraform state bucket: gs://$STATE_BUCKET"
    read -p "Are you sure you want to proceed? (y/N): " confirm

    if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
        echo "MCP deletion cancelled."
        exit 0
    fi
}

terraform_init() {
    local stack_dir="$1"
    local state_prefix="$2"

    terraform -chdir="$stack_dir" init -reconfigure \
        -backend-config="bucket=${STATE_BUCKET}" \
        -backend-config="prefix=${state_prefix}"
}



destroy_stack() {
    local stack_name="$1"
    local state_prefix="$2"
    local stack_region="$3"
    local stack_dir="$REPO_ROOT/terraform/$stack_name"

    if [ ! -d "$stack_dir" ]; then
        echo "Warning: Directory $stack_dir not found. Skipping $stack_name."
        return 0
    fi

    echo "---------------------------------------"
    echo "Destroying MCP Terraform stack: $stack_name (Region: $stack_region)"
    echo "State prefix: $state_prefix"

    terraform_init "$stack_dir" "$state_prefix"

    echo "Resources currently tracked in state:"
    if ! terraform -chdir="$stack_dir" state list >/dev/null 2>&1; then
        echo "Warning: Failed to read state or state is empty. Attempting destroy anyway, but this may fail gracefully."
    else
        terraform -chdir="$stack_dir" state list || true
    fi


    echo "Creating destroy plan for $stack_name..."
    export TF_VAR_landing_zone_bucket="${PROJECT_ID}-ai-agent-landing-zone"
    export TF_VAR_kb_ingestion_bucket="${PROJECT_ID}-kb-landing-zone"
    terraform -chdir="$stack_dir" plan -destroy -var="project_id=$PROJECT_ID" -var="main_region=$stack_region" -out=tf-destroy.plan || { echo "Warning: Failed to create plan for $stack_name. Skipping."; return 0; }

    echo "Applying destroy plan for $stack_name..."
    terraform -chdir="$stack_dir" apply tf-destroy.plan || { echo "Warning: Failed to apply destroy for $stack_name."; return 0; }
}

confirm_destroy

echo "---------------------------------------"
echo "Configuring gcloud project and Terraform impersonation..."
gcloud config set project "$PROJECT_ID"

SERVER_LIST=()
if [[ "$SERVERS_TO_DELETE" == "all" ]]; then
    # Find all directories matching *_mcp_server_resources
    for dir in "$REPO_ROOT/terraform/"*_mcp_server_resources; do
        if [ -d "$dir" ]; then
            base=$(basename "$dir")
            prefix="${base%_mcp_server_resources}"
            SERVER_LIST+=("$prefix")
        fi
    done
else
    IFS=',' read -ra SERVER_LIST <<< "$SERVERS_TO_DELETE"
fi

for SERVER_ENTRY in "${SERVER_LIST[@]}"; do
    # Extract specific region if provided (e.g. gcs=us-east1)
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
    
    # Generate state prefix dynamically.
    SERVER_BASE_HYPHEN="${SERVER_BASE//_/-}"
    STATE_PREFIX="terraform/state/${SERVER_BASE_HYPHEN}-mcp-server-resources"
    
    destroy_stack "$STACK_NAME" "$STATE_PREFIX" "$SERVER_REGION"
done

echo "---------------------------------------"
echo "MCP server deletion complete."
