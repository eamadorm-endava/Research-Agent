#!/bin/bash

set -euo pipefail

# One-time Cloud Build trigger setup for AI Agent and MCP servers (BQ + GCS + Drive).
# It is safe to re-run: existing triggers are detected and skipped.

PROJECT_ID="${PROJECT_ID:-p-dev-gce-60pf}"
PROJECT_NUMBER="${PROJECT_NUMBER:-$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')}"

SA_NAME="${SA_NAME:-terraform-sa-gemini-project}"
SA_EMAIL="${SA_EMAIL:-${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"

GITHUB_REGION="${GITHUB_REGION:-us-central1}"
GITHUB_CONNECTION_NAME="${GITHUB_CONNECTION_NAME:-eamadorm-github}"
REPOSITORY_SLUG="${REPOSITORY_SLUG:-eamadorm-endava-Research-Agent}"

PR_TARGET_BRANCH_REGEX="${PR_TARGET_BRANCH_REGEX:-^main$}"
PUSH_BRANCH_REGEX="${PUSH_BRANCH_REGEX:-^main$}"
FORCE_RECREATE="${FORCE_RECREATE:-false}"

REPO_PATH="projects/${PROJECT_NUMBER}/locations/${GITHUB_REGION}/connections/${GITHUB_CONNECTION_NAME}/repositories/${REPOSITORY_SLUG}"

echo "Creating MCP Cloud Build triggers in project: ${PROJECT_ID}"
echo "Using repository connection path: ${REPO_PATH}"
echo "Force recreate existing triggers: ${FORCE_RECREATE}"

trigger_exists() {
  local name="$1"
  gcloud builds triggers describe "$name" \
    --project="$PROJECT_ID" \
    --region="$GITHUB_REGION" >/dev/null 2>&1
}

delete_trigger() {
  local name="$1"
  gcloud builds triggers delete "$name" \
    --project="$PROJECT_ID" \
    --region="$GITHUB_REGION" \
    --quiet
}

create_trigger() {
  local name="$1"
  local type="$2"
  local dir="$3"
  local config="$4"
  local extra_dir="$5"

  local included_files="${dir}/**"
  if [[ -n "$extra_dir" ]]; then
    included_files="${included_files},${extra_dir}"
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
      --region="$GITHUB_REGION" \
      --repository="$REPO_PATH" \
      --pull-request-pattern="$PR_TARGET_BRANCH_REGEX" \
      --build-config="$config" \
      --included-files="$included_files" \
      --service-account="projects/$PROJECT_ID/serviceAccounts/$SA_EMAIL" \
      --substitutions="_SA_NAME=$SA_NAME"
  else
    echo "Creating push trigger: ${name}"
    gcloud alpha builds triggers create github \
      --name="$name" \
      --project="$PROJECT_ID" \
      --region="$GITHUB_REGION" \
      --repository="$REPO_PATH" \
      --branch-pattern="$PUSH_BRANCH_REGEX" \
      --build-config="$config" \
      --included-files="$included_files" \
      --service-account="projects/$PROJECT_ID/serviceAccounts/$SA_EMAIL" \
      --substitutions="_SA_NAME=$SA_NAME"
  fi
}

# --- AI Agent Triggers ---
# CI (Plan) on Pull Request
create_trigger "ai-agent-services-plan" "pr" "terraform/ai_agent_resources" "terraform/ai_agent_resources/ai-agent-services-cloud-build-ci.yaml" "agent/**"
# CD (Apply) on Push/Merge
create_trigger "ai-agent-services-apply" "push" "terraform/ai_agent_resources" "terraform/ai_agent_resources/ai-agent-services-cloud-build-cd.yaml" "agent/**"

# --- MCP Server Triggers ---
# BigQuery MCP triggers
create_trigger "bq-mcp-server-services-plan" "pr" "terraform/bq_mcp_server_resources" "terraform/bq_mcp_server_resources/mcp-server-services-cloud-build-ci.yaml" "mcp_servers/big_query/**"
create_trigger "bq-mcp-server-services-apply" "push" "terraform/bq_mcp_server_resources" "terraform/bq_mcp_server_resources/mcp-server-services-cloud-build-cd.yaml" "mcp_servers/big_query/**"

# GCS MCP triggers
create_trigger "gcs-mcp-server-services-plan" "pr" "terraform/gcs_mcp_server_resources" "terraform/gcs_mcp_server_resources/mcp-server-services-cloud-build-ci.yaml" "mcp_servers/gcs/**"
create_trigger "gcs-mcp-server-services-apply" "push" "terraform/gcs_mcp_server_resources" "terraform/gcs_mcp_server_resources/mcp-server-services-cloud-build-cd.yaml" "mcp_servers/gcs/**"

# Drive MCP triggers
create_trigger "drive-mcp-server-services-plan" "pr" "terraform/drive_mcp_server_resources" "terraform/drive_mcp_server_resources/mcp-server-services-cloud-build-ci.yaml" "mcp_servers/google_drive/**"
create_trigger "drive-mcp-server-services-apply" "push" "terraform/drive_mcp_server_resources" "terraform/drive_mcp_server_resources/mcp-server-services-cloud-build-cd.yaml" "mcp_servers/google_drive/**"

echo "Done. All AI Agent and MCP triggers are created (or already existed)."
