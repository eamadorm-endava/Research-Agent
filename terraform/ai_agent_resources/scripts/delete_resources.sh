#!/bin/bash
# scripts/delete_resources.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DELETE_AI_AGENT="false"
DELETE_GE_APP="false"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --delete-ai-agent) DELETE_AI_AGENT="$2"; shift ;;
        --delete-ge-app) DELETE_GE_APP="$2"; shift ;;
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

echo "This will destroy all AI Agent resources in project: $PROJECT_ID"
echo "Parameters:"
echo "  - Delete AI Agent: $DELETE_AI_AGENT"
echo "  - Delete GE App: $DELETE_GE_APP"
echo "  - GE Location: $GE_LOCATION"
echo "  - Agent Engine Location: $AGENT_ENGINE_LOCATION"
echo "  - GE App ID: $GE_APP_ID"
echo "  - Agent Display Name: $AGENT_DISPLAY_NAME"
echo "  - Auth Secret Names: $GE_AUTH_ID_SECRET_NAMES"
read -p "Are you sure you want to proceed? (y/N): " confirm

if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo "--- Starting AI Agent resource cleanup ---"

CURRENT_STEP=1

if [[ "$DELETE_AI_AGENT" == "true" ]]; then
    # 1. Unregister the agent in Gemini Enterprise
    echo "[Step $CURRENT_STEP] Unregistering agent from Gemini Enterprise..."
    ((CURRENT_STEP++))
    bash "$SCRIPT_DIR/ge_agent_manager.sh" delete-agent \
        --project "$PROJECT_ID" \
        --app-id "$GE_APP_ID" \
        --agent-display-name "$AGENT_DISPLAY_NAME" \
        --ge-location "$GE_LOCATION"

    # 2. Delete the auth resource in Gemini Enterprise
    echo "[Step $CURRENT_STEP] Resolving authentication resource IDs from Secret Manager..."
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
        echo "[Step $CURRENT_STEP continued] Deleting authentication resources: $RESOLVED_AUTH_IDS"
        bash "$SCRIPT_DIR/ge_agent_manager.sh" delete-auth-ids \
            --project "$PROJECT_ID" \
            --auth-ids "$RESOLVED_AUTH_IDS" \
            --ge-location "$GE_LOCATION"
    else
        echo "[Step $CURRENT_STEP skipped] No Auth IDs were resolved from Secret Manager."
    fi
    ((CURRENT_STEP++))
fi

if [[ "$DELETE_GE_APP" == "true" ]]; then
    # 3. Delete the App in Gemini Enterprise (Discovery Engine)
    echo "[Step $CURRENT_STEP] Deleting App (Engine) in Gemini Enterprise..."
    ((CURRENT_STEP++))
    if [ "$GE_LOCATION" == "global" ]; then
        API_ENDPOINT="discoveryengine.googleapis.com"
    else
        API_ENDPOINT="${GE_LOCATION}-discoveryengine.googleapis.com"
    fi

    curl -s -X DELETE \
      -H "Authorization: Bearer $(gcloud auth print-access-token)" \
      -H "x-goog-user-project: ${PROJECT_ID}" \
      "https://${API_ENDPOINT}/v1/projects/${PROJECT_ID}/locations/${GE_LOCATION}/collections/default_collection/engines/${GE_APP_ID}"
    echo ""
fi

if [[ "$DELETE_AI_AGENT" == "true" ]]; then
    # 4. Delete the agent in Agent Engine
    echo "[Step $CURRENT_STEP] Deleting Reasoning Engine in Vertex AI..."
    ((CURRENT_STEP++))
    uv run --group ai-agent python "$SCRIPT_DIR/delete_agent_engine.py" \
        --project "$PROJECT_ID" \
        --location "$AGENT_ENGINE_LOCATION" \
        --display-name "$AGENT_DISPLAY_NAME" \
        --force

    # 5. Finally, make a terraform destroy
    echo "[Step $CURRENT_STEP] Executing terraform destroy..."
    ((CURRENT_STEP++))
    pushd "$SCRIPT_DIR/.." > /dev/null
    terraform init -reconfigure \
        -backend-config="bucket=${PROJECT_ID}-terraform-state" \
        -backend-config="prefix=terraform/state/ai-agent-resources"
    terraform destroy -auto-approve -var="project_id=$PROJECT_ID" -var="main_region=$AGENT_ENGINE_LOCATION"
    popd > /dev/null

    if [ -n "$GE_AUTH_ID_SECRET_NAMES" ]; then
        echo ""
        echo "[Step $CURRENT_STEP] Deleting secrets from Secret Manager..."
        ((CURRENT_STEP++))
        IFS=',' read -ra SECRET_ARRAY <<< "$GE_AUTH_ID_SECRET_NAMES"
        for SECRET in "${SECRET_ARRAY[@]}"; do
            if [ -n "$SECRET" ]; then
                echo "Deleting secret: $SECRET"
                gcloud secrets delete "$SECRET" --project "$PROJECT_ID" --quiet || echo "Warning: Failed to delete $SECRET or it doesn't exist."
            fi
        done
    fi
fi

echo "--- Cleanup completed successfully! ---"
