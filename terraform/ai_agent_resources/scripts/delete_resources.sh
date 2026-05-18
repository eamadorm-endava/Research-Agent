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
        --auth-id) AUTH_ID="$2"; shift ;;
        --engine-id) ENGINE_ID="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Mandatory parameter validation
if [ -z "$PROJECT_ID" ] || [ -z "$APP_ID" ] || [ -z "$AGENT_DISPLAY_NAME" ] || [ -z "$AUTH_ID" ] || [ -z "$ENGINE_ID" ]; then
    echo "Error: Missing mandatory parameters."
    echo "Usage: $0 --project <ID> --app-id <ID> --agent-display-name <NAME> --auth-id <ID> --engine-id <ID> [--location <REGION>]"
    exit 1
fi

echo "--- Starting AI Agent resource cleanup ---"

# 1. Unregister the agent in Gemini Enterprise
echo "[Step 1/4] Unregistering agent from Gemini Enterprise..."
bash "$SCRIPT_DIR/ge_agent_manager.sh" delete-agent \
    --project "$PROJECT_ID" \
    --app-id "$APP_ID" \
    --agent-display-name "$AGENT_DISPLAY_NAME" \
    --ge-location "$GE_LOCATION"

# 2. Delete the auth resource in Gemini Enterprise
echo "[Step 2/4] Deleting authentication resource in Gemini Enterprise..."
bash "$SCRIPT_DIR/ge_agent_manager.sh" delete-auth-ids \
    --project "$PROJECT_ID" \
    --auth-ids "$AUTH_ID" \
    --ge-location "$GE_LOCATION"

# 3. Delete the agent in Agent Engine
echo "[Step 3/4] Deleting Reasoning Engine in Vertex AI..."
uv run --group ai-agent python "$SCRIPT_DIR/delete_agent_engine.py" \
    --project "$PROJECT_ID" \
    --location "$LOCATION" \
    --engine-id "$ENGINE_ID" \
    --force

# 4. Finally, make a terraform destroy
echo "[Step 4/4] Executing terraform destroy..."
pushd "$SCRIPT_DIR/.." > /dev/null
terraform destroy -auto-approve -var="project_id=$PROJECT_ID"
popd > /dev/null

echo "--- Cleanup completed successfully! ---"
echo ""
echo "IMPORTANT: Please remember to manually delete the App in the Gemini Enterprise (Discovery Engine) Console"
echo ""
