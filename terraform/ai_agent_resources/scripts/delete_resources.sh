#!/bin/bash
# scripts/delete_resources.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --project) PROJECT_ID="$2"; shift ;; # The GCP Project ID where resources are located
        --ge-location) GE_LOCATION="$2"; shift ;; # The location of the Gemini Enterprise resources
        --agent-engine-location) AGENT_ENGINE_LOCATION="$2"; shift ;; # The GCP Region for the Vertex AI Agent Engine
        --ge-app-id) GE_APP_ID="$2"; shift ;; # The Discovery Engine App ID in Gemini Enterprise
        --agent-display-name) AGENT_DISPLAY_NAME="$2"; shift ;; # The display name of the Agent (used in both GE and Vertex AI)
        --ge-auth-id-secret-names) GE_AUTH_ID_SECRET_NAMES="$2"; shift ;; # Comma-separated Secret Manager names storing GE Auth IDs
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Mandatory parameter validation
if [ -z "$PROJECT_ID" ] || [ -z "$GE_LOCATION" ] || [ -z "$AGENT_ENGINE_LOCATION" ] || [ -z "$GE_APP_ID" ] || [ -z "$AGENT_DISPLAY_NAME" ] || [ -z "$GE_AUTH_ID_SECRET_NAMES" ]; then
    echo "Error: Missing mandatory parameters."
    echo "Usage: $0 --project <ID> --ge-location <REGION> --agent-engine-location <REGION> --ge-app-id <ID> --agent-display-name <NAME> --ge-auth-id-secret-names <SECRET1,SECRET2,...>"
    exit 1
fi

echo "--- Starting AI Agent resource cleanup ---"

# 1. Unregister the agent in Gemini Enterprise
echo "[Step 1/5] Unregistering agent from Gemini Enterprise..."
bash "$SCRIPT_DIR/ge_agent_manager.sh" delete-agent \
    --project "$PROJECT_ID" \
    --app-id "$GE_APP_ID" \
    --agent-display-name "$AGENT_DISPLAY_NAME" \
    --ge-location "$GE_LOCATION"

# 2. Delete the auth resource in Gemini Enterprise
echo "[Step 2/5] Resolving authentication resource IDs from Secret Manager..."
RESOLVED_AUTH_IDS=""
IFS=',' read -ra SECRET_ARRAY <<< "$GE_AUTH_ID_SECRET_NAMES"
for SECRET in "${SECRET_ARRAY[@]}"; do
    if [ -n "$SECRET" ]; then
        echo "Fetching value for secret: $SECRET"
        AUTH_VAL=$(gcloud secrets versions access latest --secret="$SECRET" --project="$PROJECT_ID" 2>/dev/null || echo "")
        if [ -n "$AUTH_VAL" ]; then
            if [ -n "$RESOLVED_AUTH_IDS" ]; then
                RESOLVED_AUTH_IDS="${RESOLVED_AUTH_IDS},${AUTH_VAL}"
            else
                RESOLVED_AUTH_IDS="${AUTH_VAL}"
            fi
        else
            echo "Warning: Could not resolve secret $SECRET (it may have been deleted already)."
        fi
    fi
done

if [ -n "$RESOLVED_AUTH_IDS" ]; then
    echo "[Step 2/5 continued] Deleting authentication resources: $RESOLVED_AUTH_IDS"
    bash "$SCRIPT_DIR/ge_agent_manager.sh" delete-auth-ids \
        --project "$PROJECT_ID" \
        --auth-ids "$RESOLVED_AUTH_IDS" \
        --ge-location "$GE_LOCATION"
else
    echo "[Step 2/5 skipped] No Auth IDs were resolved from Secret Manager."
fi

# 3. Delete the App in Gemini Enterprise (Discovery Engine)
echo "[Step 3/5] Deleting App (Engine) in Gemini Enterprise..."
curl -s -X DELETE \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "x-goog-user-project: ${PROJECT_ID}" \
  "https://discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_ID}/locations/${GE_LOCATION}/collections/default_collection/engines/${GE_APP_ID}"
echo ""

# 4. Delete the agent in Agent Engine
echo "[Step 4/5] Deleting Reasoning Engine in Vertex AI..."
uv run --group ai-agent python "$SCRIPT_DIR/delete_agent_engine.py" \
    --project "$PROJECT_ID" \
    --location "$AGENT_ENGINE_LOCATION" \
    --display-name "$AGENT_DISPLAY_NAME" \
    --force

# 5. Finally, make a terraform destroy
echo "[Step 5/5] Executing terraform destroy..."
pushd "$SCRIPT_DIR/.." > /dev/null
terraform destroy -auto-approve -var="project_id=$PROJECT_ID"
popd > /dev/null

if [ -n "$GE_AUTH_ID_SECRET_NAMES" ]; then
    echo ""
    echo "[Step 6] Deleting secrets from Secret Manager..."
    IFS=',' read -ra SECRET_ARRAY <<< "$GE_AUTH_ID_SECRET_NAMES"
    for SECRET in "${SECRET_ARRAY[@]}"; do
        if [ -n "$SECRET" ]; then
            echo "Deleting secret: $SECRET"
            gcloud secrets delete "$SECRET" --project "$PROJECT_ID" --quiet || echo "Warning: Failed to delete $SECRET or it doesn't exist."
        fi
    done
fi

echo "--- Cleanup completed successfully! ---"
