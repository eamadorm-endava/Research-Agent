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
#
# It intentionally does not destroy shared resources, the AI Agent, the EKB
# pipeline, the Terraform state bucket, or the Terraform service account.
#
# Run this script from the repository root:
#   ./terraform/scripts/delete_mcp_servers.sh
#
# Optional environment variable overrides:
#   PROJECT_ID=your-project-id
#   REGION=us-central1
#   SA_NAME=terraform-sa-gemini-project
#   STATE_BUCKET=your-terraform-state-bucket
#   DELETE_MCP_TRIGGERS=true
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- Configuration ---
PROJECT_ID="${PROJECT_ID:-ag-core-ops-auj0}"
REGION="${REGION:-us-central1}"
SA_NAME="${SA_NAME:-terraform-sa-gemini-project}"
SA_EMAIL="${SA_EMAIL:-${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
STATE_BUCKET="${STATE_BUCKET:-${PROJECT_ID}-terraform-state}"
DELETE_MCP_TRIGGERS="${DELETE_MCP_TRIGGERS:-false}"

# Terraform should impersonate the same service account that created the stacks.
export GOOGLE_IMPERSONATE_SERVICE_ACCOUNT="$SA_EMAIL"

# MCP Terraform stacks and their remote state prefixes.
# The backend prefixes must match the prefixes used by the Cloud Build pipelines.
MCP_STACKS=(
    "gcs_mcp_server_resources:terraform/state/gcs-mcp-server-resources"
    "bq_mcp_server_resources:terraform/state/bq-mcp-server-resources"
    "drive_mcp_server_resources:terraform/state/drive-mcp-server-resources"
    "google_calendar_mcp_server_resources:terraform/state/calendar-mcp-server-resources"
)

# Optional MCP Cloud Build triggers. They are deleted only when
# DELETE_MCP_TRIGGERS=true is set by the caller.
MCP_TRIGGERS=(
    "bq-mcp-server-services-plan"
    "bq-mcp-server-services-apply"
    "gcs-mcp-server-services-plan"
    "gcs-mcp-server-services-apply"
    "drive-mcp-server-services-plan"
    "drive-mcp-server-services-apply"
    "calendar-mcp-server-services-plan"
    "calendar-mcp-server-services-apply"
)

confirm_destroy() {
    echo "This will destroy all MCP server Terraform resources in project: $PROJECT_ID"
    echo "Terraform service account: $SA_EMAIL"
    echo "Terraform state bucket: gs://$STATE_BUCKET"
    echo "MCP Cloud Build triggers will be deleted: $DELETE_MCP_TRIGGERS"
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
        -backend-config="prefix=${state_prefix}" \
        -backend-config="impersonate_service_account=${SA_EMAIL}"
}

disable_cloud_run_deletion_protection() {
    local stack_dir="$1"

    # Cloud Run services cannot be destroyed until deletion_protection=false has
    # already been applied. This targeted apply updates that setting before the
    # full destroy plan is created.
    local target="module.mcp_server_cloud_run.google_cloud_run_v2_service.service[0]"

    if terraform -chdir="$stack_dir" state list | grep -F -q "${target}"; then
        echo "Disabling Cloud Run deletion protection for: $stack_dir"
        terraform -chdir="$stack_dir" apply \
            -target="$target" \
            -auto-approve
    else
        echo "Cloud Run service is not present in state for $stack_dir, skipping deletion protection update."
    fi
}

destroy_stack() {
    local stack_name="$1"
    local state_prefix="$2"
    local stack_dir="$REPO_ROOT/terraform/$stack_name"

    echo "---------------------------------------"
    echo "Destroying MCP Terraform stack: $stack_name"
    echo "State prefix: $state_prefix"

    terraform_init "$stack_dir" "$state_prefix"

    echo "Resources currently tracked in state:"
    terraform -chdir="$stack_dir" state list || true

    disable_cloud_run_deletion_protection "$stack_dir"

    echo "Creating destroy plan for $stack_name..."
    terraform -chdir="$stack_dir" plan -destroy -out=tf-destroy.plan

    echo "Applying destroy plan for $stack_name..."
    terraform -chdir="$stack_dir" apply tf-destroy.plan
}

delete_mcp_triggers() {
    echo "---------------------------------------"
    echo "Deleting MCP Cloud Build triggers..."

    for TRIGGER in "${MCP_TRIGGERS[@]}"; do
        if gcloud builds triggers describe "$TRIGGER" --region="$REGION" --project="$PROJECT_ID" > /dev/null 2>&1; then
            echo "Deleting trigger: $TRIGGER..."
            gcloud alpha builds triggers delete "$TRIGGER" --region="$REGION" --project="$PROJECT_ID" --quiet
        else
            echo "Trigger $TRIGGER not found, skipping."
        fi
    done

    echo "MCP trigger cleanup complete."
}

confirm_destroy

echo "---------------------------------------"
echo "Configuring gcloud project and Terraform impersonation..."
gcloud config set project "$PROJECT_ID"

for STACK in "${MCP_STACKS[@]}"; do
    STACK_NAME="${STACK%%:*}"
    STATE_PREFIX="${STACK#*:}"
    destroy_stack "$STACK_NAME" "$STATE_PREFIX"
done

if [[ "$DELETE_MCP_TRIGGERS" == "true" ]]; then
    delete_mcp_triggers
else
    echo "Skipping MCP Cloud Build trigger deletion. Set DELETE_MCP_TRIGGERS=true to delete them."
fi

echo "---------------------------------------"
echo "MCP server deletion complete."
