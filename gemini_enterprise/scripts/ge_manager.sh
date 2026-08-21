#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# Gemini Enterprise Manager CLI
# -----------------------------------------------------------------------------
# Utility script to manage Gemini Enterprise (Discovery Engine) Apps,
# OAuth Authorizations, and ADK Agent Registrations.
# -----------------------------------------------------------------------------

COMMAND="${1:-}"
if [ -z "$COMMAND" ]; then
    echo "Error: Command is required."
    echo "Usage: $0 {create-ge-app|delete-ge-app|create-auth-ids|delete-auth-ids|register-agent|unregister-agent} [flags]"
    exit 1
fi
shift

# Default parameter values
PROJECT_ID=""
GE_LOCATION="global"
APP_ID=""
AGENT_DISPLAY_NAME=""
AGENT_DESCRIPTION=""
GE_AGENT_DESCRIPTION="Agent capable of searching and retrieving information from Google Drive, GCP, BigQuery and GCS using enterprise credentials."
ICON_URI="https://yt3.googleusercontent.com/lufyX7Ule20Ss0fpVdiFbRn8LfdUlKK2SpG2vHbRw2xQRlpG0egcgnepZvmD26wwdETKad4VcaA=s900-c-k-c0x00ffffff-no-rj"
PROMPT_TYPE="consent"
AUTH_IDS=""
CLIENT_ID=""
CLIENT_SECRET=""
OAUTH_SCOPES=""
AUTH_URI_BASE=""
AUTH_URI_EXTRAS=""
TOKEN_URI=""
AGENT_ENGINE_AGENT_ID=""
AGENT_ENGINE_LOCATION="us-central1"

# Parse CLI flags
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --project) PROJECT_ID="$2"; shift ;;
        --ge-location) GE_LOCATION="$2"; shift ;;
        --app-id|--ge-app-id) APP_ID="$2"; shift ;;
        --agent-display-name) AGENT_DISPLAY_NAME="$2"; shift ;;
        --agent-description) AGENT_DESCRIPTION="$2"; shift ;;
        --icon-uri) ICON_URI="$2"; shift ;;
        --auth-ids) AUTH_IDS="$2"; shift ;;
        --client-id) CLIENT_ID="$2"; shift ;;
        --client-secret) CLIENT_SECRET="$2"; shift ;;
        --scopes) OAUTH_SCOPES="$2"; shift ;;
        --auth-uri-base) AUTH_URI_BASE="$2"; shift ;;
        --auth-uri-extras) AUTH_URI_EXTRAS="$2"; shift ;;
        --token-uri) TOKEN_URI="$2"; shift ;;
        --prompt) PROMPT_TYPE="$2"; shift ;;
        --agent-engine-agent-id) AGENT_ENGINE_AGENT_ID="$2"; shift ;;
        --agent-engine-location) AGENT_ENGINE_LOCATION="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# Validate required global parameter
if [ -z "$PROJECT_ID" ]; then
    echo "Error: --project is required."
    exit 1
fi

AUTH_HEADER="Authorization: Bearer $(gcloud auth print-access-token)"

if [ "$GE_LOCATION" = "global" ]; then
    API_ENDPOINT="discoveryengine.googleapis.com"
else
    API_ENDPOINT="${GE_LOCATION}-discoveryengine.googleapis.com"
fi

BASE_URL="https://${API_ENDPOINT}/v1alpha/projects/${PROJECT_ID}/locations/${GE_LOCATION}"

case "$COMMAND" in
    create-ge-app)
        if [ -z "$APP_ID" ]; then
            echo "Error: --app-id (or --ge-app-id) is required for create-ge-app."
            exit 1
        fi
        
        echo "Checking if Gemini Enterprise App (Engine: ${APP_ID}) exists in ${GE_LOCATION}..."
        
        HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "$AUTH_HEADER" \
            -H "X-Goog-User-Project: $PROJECT_ID" \
            "https://${API_ENDPOINT}/v1/projects/$PROJECT_ID/locations/$GE_LOCATION/collections/default_collection/engines/$APP_ID" || true)
          
        if [ "$HTTP_STATUS" -eq 200 ]; then
            echo "Gemini Enterprise App (Engine) '$APP_ID' already exists. Skipping creation."
        elif [ "$HTTP_STATUS" -eq 404 ]; then
            echo "App (Engine) '$APP_ID' not found. Creating..."
            ENG_RES=$(curl -s -w "\n%{http_code}" -X POST \
                -H "$AUTH_HEADER" \
                -H "Content-Type: application/json" \
                -H "X-Goog-User-Project: $PROJECT_ID" \
                "https://${API_ENDPOINT}/v1/projects/$PROJECT_ID/locations/$GE_LOCATION/collections/default_collection/engines?engineId=$APP_ID" \
                -d "{
                    \"displayName\": \"$APP_ID\",
                    \"dataStoreIds\": [],
                    \"solutionType\": \"SOLUTION_TYPE_SEARCH\",
                    \"industryVertical\": \"GENERIC\",
                    \"appType\": \"APP_TYPE_INTRANET\"
                }")
            if [ "$ENG_RES_CODE" -eq 409 ]; then
                echo "Gemini Enterprise App '$APP_ID' already exists (409 Conflict). Skipping creation."
            elif [ "$ENG_RES_CODE" -ne 200 ] && [ "$ENG_RES_CODE" -ne 201 ] && [ "$ENG_RES_CODE" -ne 202 ]; then
                echo "Failed to create Engine. HTTP Status: $ENG_RES_CODE. Response: $(echo "$ENG_RES" | sed '$d')"
                exit 1
            else
                echo "Gemini Enterprise App with ID: $APP_ID created successfully."
            fi
        else
            echo "Failed to check app status. HTTP Status Code: $HTTP_STATUS"
            exit 1
        fi
        ;;

    delete-ge-app)
        if [ -z "$APP_ID" ]; then
            echo "Error: --app-id (or --ge-app-id) is required for delete-ge-app."
            exit 1
        fi
        
        echo "Deleting Gemini Enterprise App (Engine: ${APP_ID})..."
        DEL_RES=$(curl -s -w "\n%{http_code}" -X DELETE \
            -H "$AUTH_HEADER" \
            -H "X-Goog-User-Project: $PROJECT_ID" \
            "https://${API_ENDPOINT}/v1/projects/$PROJECT_ID/locations/$GE_LOCATION/collections/default_collection/engines/$APP_ID" || true)
        DEL_RES_CODE=$(echo "$DEL_RES" | tail -n 1)
        
        if [ "$DEL_RES_CODE" -ne 200 ] && [ "$DEL_RES_CODE" -ne 202 ] && [ "$DEL_RES_CODE" -ne 204 ] && [ "$DEL_RES_CODE" -ne 404 ]; then
            echo "Failed to delete Engine. HTTP Status: $DEL_RES_CODE. Response: $(echo "$DEL_RES" | sed '$d')"
            exit 1
        fi
        echo "Gemini Enterprise App with ID: $APP_ID deleted successfully (or already absent)."
        ;;

    create-auth-ids)
        if [ -z "$AUTH_IDS" ] || [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ] || [ -z "$OAUTH_SCOPES" ] || [ -z "$AUTH_URI_BASE" ] || [ -z "$TOKEN_URI" ]; then
            echo "Error: Missing required parameters for create-auth-ids."
            exit 1
        fi
        
        ENCODED_SCOPES="${OAUTH_SCOPES// /%20}"
        AUTH_URI="${AUTH_URI_BASE}?client_id=${CLIENT_ID}&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Fstatic%2Foauth%2Foauth.html&scope=${ENCODED_SCOPES}&response_type=code&prompt=${PROMPT_TYPE}"
        if [ -n "$AUTH_URI_EXTRAS" ]; then
            AUTH_URI="${AUTH_URI}&${AUTH_URI_EXTRAS}"
        fi

        JSON_PAYLOAD=$(jq -n \
            --arg clientId "$CLIENT_ID" \
            --arg clientSecret "$CLIENT_SECRET" \
            --arg authUri "$AUTH_URI" \
            --arg tokenUri "$TOKEN_URI" \
            '{
                "serverSideOauth2": {
                    "clientId": $clientId,
                    "clientSecret": $clientSecret,
                    "authorizationUri": $authUri,
                    "tokenUri": $tokenUri
                }
            }')

        IFS=',' read -ra ID_ARRAY <<< "$AUTH_IDS"
        for ID in "${ID_ARRAY[@]}"; do
            if [ -z "$ID" ]; then continue; fi
            CREATE_AUTH_URL="${BASE_URL}/authorizations?authorizationId=${ID}"
            echo "Creating Auth ID ${ID} in GE..."
            CREATE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
                -H "$AUTH_HEADER" \
                -H "Content-Type: application/json" \
                -H "X-Goog-User-Project: ${PROJECT_ID}" \
                "$CREATE_AUTH_URL" -d "$JSON_PAYLOAD")
            CREATE_CODE=$(echo "$CREATE_RESPONSE" | tail -n 1)
            if [ "$CREATE_CODE" -eq 409 ]; then
                echo "Auth ID $ID already exists in GE (409 Conflict). Skipping creation."
            elif [ "$CREATE_CODE" -ne 200 ] && [ "$CREATE_CODE" -ne 201 ] && [ "$CREATE_CODE" -ne 202 ]; then
                echo "Failed to create Auth ID $ID. HTTP Status: $CREATE_CODE. Response: $(echo "$CREATE_RESPONSE" | sed '$d')"
                exit 1
            else
                echo "Auth ID $ID created successfully."
            fi
        done
        ;;

    delete-auth-ids)
        if [ -z "$AUTH_IDS" ]; then
            echo "Error: --auth-ids is required for delete-auth-ids."
            exit 1
        fi
        IFS=',' read -ra ID_ARRAY <<< "$AUTH_IDS"
        for ID in "${ID_ARRAY[@]}"; do
            if [ -z "$ID" ]; then continue; fi
            AUTH_ID_URL="${BASE_URL}/authorizations/${ID}"
            echo "Deleting Auth ID ${ID} from GE..."
            DELETE_RESPONSE=$(curl -s -w "\n%{http_code}" -X DELETE -H "$AUTH_HEADER" "$AUTH_ID_URL" || true)
            DEL_CODE=$(echo "$DELETE_RESPONSE" | tail -n 1)
            if [ "$DEL_CODE" -ne 200 ] && [ "$DEL_CODE" -ne 202 ] && [ "$DEL_CODE" -ne 204 ] && [ "$DEL_CODE" -ne 404 ]; then
                echo "Failed to delete Auth ID. HTTP Status: $DEL_CODE. Response: $(echo "$DELETE_RESPONSE" | sed '$d')"
                exit 1
            fi
            echo "Auth ID ${ID} deleted (or not present)."
        done
        ;;

    register-agent)
        if [ -z "$APP_ID" ] || [ -z "$AGENT_DISPLAY_NAME" ] || [ -z "$AGENT_ENGINE_LOCATION" ]; then
            echo "Error: --app-id, --agent-display-name, and --agent-engine-location are required for register-agent."
            exit 1
        fi

        # Resolution Layer: Fallback to query Vertex AI if AGENT_ENGINE_AGENT_ID is not passed
        if [ -z "$AGENT_ENGINE_AGENT_ID" ]; then
            echo "Agent Engine ID not provided. Querying Vertex AI Reasoning Engines for display name: '${AGENT_DISPLAY_NAME}'..."
            AGENT_ENGINE_AGENT_ID=$(gcloud ai reasoning-engines list \
                --project="$PROJECT_ID" \
                --region="$AGENT_ENGINE_LOCATION" \
                --filter="displayName=\"${AGENT_DISPLAY_NAME}\"" \
                --format="value(name)" 2>/dev/null | head -n 1 | awk -F'/' '{print $NF}' || echo "")
            
            if [ -z "$AGENT_ENGINE_AGENT_ID" ]; then
                echo "Error: Could not locate active Vertex AI Reasoning Engine with display name '${AGENT_DISPLAY_NAME}' in ${AGENT_ENGINE_LOCATION}."
                exit 1
            fi
            echo "Resolved Agent Engine ID dynamically: ${AGENT_ENGINE_AGENT_ID}"
        fi
        
        PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
        AGENTS_URL="${BASE_URL}/collections/default_collection/engines/${APP_ID}/assistants/default_assistant/agents"
        REASONING_ENGINE_PATH="projects/${PROJECT_ID}/locations/${AGENT_ENGINE_LOCATION}/reasoningEngines/${AGENT_ENGINE_AGENT_ID}"
        
        DESCRIPTION="${AGENT_DESCRIPTION:-$GE_AGENT_DESCRIPTION}"

        AUTH_ARRAY_JSON="[]"
        if [ -n "$AUTH_IDS" ]; then
            AUTH_ARRAY_JSON=$(echo "$AUTH_IDS" | jq -R -c 'split(",") | map(select(length > 0) | "projects/'"${PROJECT_NUMBER}"'/locations/'"${GE_LOCATION}"'/authorizations/" + .)')
        fi
        
        echo "Registering Agent '${AGENT_DISPLAY_NAME}' (Reasoning Engine: ${AGENT_ENGINE_AGENT_ID}) into Gemini Enterprise App '${APP_ID}'..."
        
        JSON_PAYLOAD=$(jq -n \
            --arg displayName "$AGENT_DISPLAY_NAME" \
            --arg adkResourceId "$REASONING_ENGINE_PATH" \
            --arg description "$DESCRIPTION" \
            --arg iconUri "$ICON_URI" \
            --argjson authIds "$AUTH_ARRAY_JSON" \
            '{
                "displayName": $displayName,
                "description": $description,
                "icon": {
                    "uri": $iconUri
                },
                "adk_agent_definition": {
                    "provisioned_reasoning_engine": {
                        "reasoning_engine": $adkResourceId
                    }
                },
                "authorization_config": {
                    "tool_authorizations": $authIds
                }
            }')

        REG_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
            -H "$AUTH_HEADER" \
            -H "Content-Type: application/json" \
            -H "X-Goog-User-Project: ${PROJECT_ID}" \
            "$AGENTS_URL" -d "$JSON_PAYLOAD")
        REG_CODE=$(echo "$REG_RESPONSE" | tail -n 1)
        if [ "$REG_CODE" -ne 200 ] && [ "$REG_CODE" -ne 201 ] && [ "$REG_CODE" -ne 202 ]; then
            echo "Failed to register Agent in GE. HTTP Status: $REG_CODE. Response: $(echo "$REG_RESPONSE" | sed '$d')"
            exit 1
        fi
        echo "Agent '${AGENT_DISPLAY_NAME}' registered successfully in Gemini Enterprise."
        ;;

    unregister-agent)
        if [ -z "$APP_ID" ] || [ -z "$AGENT_DISPLAY_NAME" ]; then
            echo "Error: --app-id and --agent-display-name are required for unregister-agent."
            exit 1
        fi
        echo "Looking up agent with display name '${AGENT_DISPLAY_NAME}' in GE App '${APP_ID}'..."
        AGENTS_URL="${BASE_URL}/collections/default_collection/engines/${APP_ID}/assistants/default_assistant/agents"
        
        HTTP_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET -H "$AUTH_HEADER" "$AGENTS_URL" || true)
        HTTP_BODY=$(echo "$HTTP_RESPONSE" | sed '$d')
        HTTP_CODE=$(echo "$HTTP_RESPONSE" | tail -n 1)

        if [ "$HTTP_CODE" -ne 200 ]; then
            echo "Notice: Could not fetch agents list from GE (HTTP $HTTP_CODE). It may not exist yet."
            exit 0
        fi

        AGENT_RESOURCE_NAME=$(echo "$HTTP_BODY" | jq -r ".agents[]? | select(.displayName == \"${AGENT_DISPLAY_NAME}\") | .name" | head -n 1 || echo "")

        if [ -n "$AGENT_RESOURCE_NAME" ] && [ "$AGENT_RESOURCE_NAME" != "null" ]; then
            echo "Deleting Agent resource $AGENT_RESOURCE_NAME from GE..."
            DELETE_RESPONSE=$(curl -s -w "\n%{http_code}" -X DELETE -H "$AUTH_HEADER" "https://${API_ENDPOINT}/v1alpha/$AGENT_RESOURCE_NAME" || true)
            DEL_CODE=$(echo "$DELETE_RESPONSE" | tail -n 1)
            if [ "$DEL_CODE" -ne 200 ] && [ "$DEL_CODE" -ne 202 ] && [ "$DEL_CODE" -ne 204 ]; then
                echo "Warning: Failed to delete agent. HTTP Status: $DEL_CODE. Response: $(echo "$DELETE_RESPONSE" | sed '$d')"
                exit 1
            fi
            echo "Agent '${AGENT_DISPLAY_NAME}' successfully unregistered from GE."
        else
            echo "No existing agent found with display name '${AGENT_DISPLAY_NAME}' in GE App '${APP_ID}'."
        fi
        ;;

    *)
        echo "Usage: $0 {create-ge-app|delete-ge-app|create-auth-ids|delete-auth-ids|register-agent|unregister-agent} [flags]"
        exit 1
        ;;
esac
