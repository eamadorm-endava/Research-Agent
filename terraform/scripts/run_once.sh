#!/bin/bash

set -euo pipefail

# One-time Cloud Build trigger setup for MCP servers (BQ + GCS).
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

REPO_PATH="projects/${PROJECT_NUMBER}/locations/${GITHUB_REGION}/connections/${GITHUB_CONNECTION_NAME}/repositories/${REPOSITORY_SLUG}"

echo "Creating MCP Cloud Build triggers in project: ${PROJECT_ID}"
echo "Using repository connection path: ${REPO_PATH}"

trigger_exists() {
  local name="$1"
  gcloud builds triggers describe "$name" \
    --project="$PROJECT_ID" \
    --region="$GITHUB_REGION" >/dev/null 2>&1
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
    echo "Trigger already exists, skipping: ${name}"
    return
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

# BigQuery MCP triggers
create_trigger "bq-mcp-server-services-plan" "pr" "terraform/bq_mcp_server_resources" "terraform/bq_mcp_server_resources/mcp-server-services-cloud-build-ci.yaml" "mcp_servers/big_query/**"
create_trigger "bq-mcp-server-services-apply" "push" "terraform/bq_mcp_server_resources" "terraform/bq_mcp_server_resources/mcp-server-services-cloud-build-cd.yaml" "mcp_servers/big_query/**"

# GCS MCP triggers
create_trigger "gcs-mcp-server-services-plan" "pr" "terraform/gcs_mcp_server_resources" "terraform/gcs_mcp_server_resources/mcp-server-services-cloud-build-ci.yaml" "mcp_servers/gcs/**"
create_trigger "gcs-mcp-server-services-apply" "push" "terraform/gcs_mcp_server_resources" "terraform/gcs_mcp_server_resources/mcp-server-services-cloud-build-cd.yaml" "mcp_servers/gcs/**"

echo "Done. MCP triggers are created (or already existed)."
