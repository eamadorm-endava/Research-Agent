#!/bin/bash
# scripts/delete_resources.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default values
LOCATION="us-central1"
GE_LOCATION="global"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --project) PROJECT_ID="$2"; shift ;;
        --location) LOCATION="$2"; shift ;;
        --app-id) APP_ID="$2"; shift ;;
        --agent-display-name) AGENT_DISPLAY_NAME="$2"; shift ;;
        --auth-ids) AUTH_IDS="$2"; shift ;;
        --engine-id) ENGINE_ID="$2"; shift ;;
        --delete-secrets) SECRETS="$2"; shift ;;
        --oauth-clients) OAUTH_CLIENTS="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Mandatory parameter validation
if [ -z "$PROJECT_ID" ] || [ -z "$APP_ID" ] || [ -z "$AGENT_DISPLAY_NAME" ] || [ -z "$AUTH_IDS" ] || [ -z "$ENGINE_ID" ]; then
    echo "Error: Missing mandatory parameters."
    echo "Usage: $0 --project <ID> --app-id <ID> --agent-display-name <NAME> --auth-ids <ID1,ID2,...> --engine-id <ID> [--location <REGION>] [--delete-secrets <S1,S2,...>] [--oauth-clients <C1,C2,...>]"
    exit 1
fi

echo "--- Starting AI Agent resource cleanup ---"

# 1. Unregister the agent in Gemini Enterprise
echo "[Step 1/5] Unregistering agent from Gemini Enterprise..."
bash "$SCRIPT_DIR/ge_agent_manager.sh" delete-agent \
    --project "$PROJECT_ID" \
    --app-id "$APP_ID" \
    --agent-display-name "$AGENT_DISPLAY_NAME" \
    --ge-location "$GE_LOCATION"

# 2. Delete the auth resource in Gemini Enterprise
echo "[Step 2/5] Deleting authentication resource in Gemini Enterprise..."
bash "$SCRIPT_DIR/ge_agent_manager.sh" delete-auth-ids \
    --project "$PROJECT_ID" \
    --auth-ids "$AUTH_IDS" \
    --ge-location "$GE_LOCATION"

# 3. Delete the App in Gemini Enterprise (Discovery Engine)
echo "[Step 3/5] Deleting App (Engine) in Gemini Enterprise..."
curl -s -X DELETE \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "x-goog-user-project: ${PROJECT_ID}" \
  "https://discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_ID}/locations/${GE_LOCATION}/collections/default_collection/engines/${APP_ID}"
echo ""

# 4. Delete the agent in Agent Engine
echo "[Step 4/5] Deleting Reasoning Engine in Vertex AI..."
uv run --group ai-agent python "$SCRIPT_DIR/delete_agent_engine.py" \
    --project "$PROJECT_ID" \
    --location "$LOCATION" \
    --engine-id "$ENGINE_ID" \
    --force

# 5. Finally, make a terraform destroy
echo "[Step 5/5] Executing terraform destroy..."
pushd "$SCRIPT_DIR/.." > /dev/null
terraform destroy -auto-approve -var="project_id=$PROJECT_ID"
popd > /dev/null

if [ -n "$SECRETS" ]; then
    echo ""
    echo "[Step 6] Deleting secrets from Secret Manager..."
    IFS=',' read -ra SECRET_ARRAY <<< "$SECRETS"
    for SECRET in "${SECRET_ARRAY[@]}"; do
        if [ -n "$SECRET" ]; then
            echo "Deleting secret: $SECRET"
            gcloud secrets delete "$SECRET" --project "$PROJECT_ID" --quiet || echo "Warning: Failed to delete $SECRET or it doesn't exist."
        fi
    done
fi

if [ -n "$OAUTH_CLIENTS" ]; then
    echo ""
    echo "[Step 7] Deleting OAuth Clients..."
    IFS=',' read -ra CLIENT_ARRAY <<< "$OAUTH_CLIENTS"
    for CLIENT in "${CLIENT_ARRAY[@]}"; do
        if [ -n "$CLIENT" ]; then
            echo "Deleting OAuth client: $CLIENT"
            gcloud iam oauth-clients delete "$CLIENT" --project "$PROJECT_ID" --quiet || echo "Warning: Failed to delete OAuth client $CLIENT or it doesn't exist."
        fi
    done
fi

echo "--- Cleanup completed successfully! ---"
