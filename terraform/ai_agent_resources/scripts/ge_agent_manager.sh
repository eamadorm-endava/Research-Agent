#!/bin/bash
set -e

COMMAND=$1
shift

# Default values
GE_LOCATION="global"
GE_AGENT_DESCRIPTION="Agent capable of searching and retrieving information from Google Drive, GCP and GCS using user's credentials"
ICON_URI="https://yt3.googleusercontent.com/lufyX7Ule20Ss0fpVdiFbRn8LfdUlKK2SpG2vHbRw2xQRlpG0egcgnepZvmD26wwdETKad4VcaA=s900-c-k-c0x00ffffff-no-rj"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --project) PROJECT_ID="$2"; shift ;;
        --ge-location) GE_LOCATION="$2"; shift ;;
        --app-id) APP_ID="$2"; shift ;;
        --agent-display-name) AGENT_DISPLAY_NAME="$2"; shift ;;
        --auth-ids) AUTH_IDS="$2"; shift ;;
        --client-id) CLIENT_ID="$2"; shift ;;
        --client-secret) CLIENT_SECRET="$2"; shift ;;
        --scopes) OAUTH_SCOPES="$2"; shift ;;
        --auth-uri-base) AUTH_URI_BASE="$2"; shift ;;
        --auth-uri-extras) AUTH_URI_EXTRAS="$2"; shift ;;
        --token-uri) TOKEN_URI="$2"; shift ;;
        --agent-engine-agent-id) AGENT_ENGINE_AGENT_ID="$2"; shift ;;
        --agent-engine-location) AGENT_ENGINE_LOCATION="$2"; shift ;;
        --agent-description) GE_AGENT_DESCRIPTION="$2"; shift ;;
        --icon-uri) ICON_URI="$2"; shift ;;
        --agent-description) AGENT_DESCRIPTION="$2"; shift ;;
        --ge-app-id) APP_ID="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# Require PROJECT_ID for all commands
if [ -z "$PROJECT_ID" ]; then
    echo "Error: --project is required."
    exit 1
fi

AUTH_HEADER="Authorization: Bearer $(gcloud auth print-access-token)"

if [ "$GE_LOCATION" == "global" ]; then
    API_ENDPOINT="discoveryengine.googleapis.com"
else
    API_ENDPOINT="${GE_LOCATION}-discoveryengine.googleapis.com"
fi

BASE_URL="https://${API_ENDPOINT}/v1alpha/projects/${PROJECT_ID}/locations/${GE_LOCATION}"

case "$COMMAND" in
    delete-agent)
        if [ -z "$APP_ID" ] || [ -z "$AGENT_DISPLAY_NAME" ]; then
            echo "Error: --app-id and --agent-display-name are required for delete-agent."
            exit 1
        fi
        echo "Looking for agent with display name: $AGENT_DISPLAY_NAME..."
        AGENTS_URL="${BASE_URL}/collections/default_collection/engines/${APP_ID}/assistants/default_assistant/agents"
        
        # We need to capture the HTTP code for error handling
        HTTP_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET -H "$AUTH_HEADER" "$AGENTS_URL")
        HTTP_BODY=$(echo "$HTTP_RESPONSE" | sed '$d')
        HTTP_CODE=$(echo "$HTTP_RESPONSE" | tail -n 1)

        if [ "$HTTP_CODE" -ne 200 ]; then
             echo "Error fetching agents. HTTP Status: $HTTP_CODE. Response: $HTTP_BODY"
             exit 1
        fi

        AGENT_ID=$(echo "$HTTP_BODY" | jq -r ".agents[]? | select(.displayName == \"${AGENT_DISPLAY_NAME}\") | .name" | head -n 1)

        if [ -n "$AGENT_ID" ] && [ "$AGENT_ID" != "null" ]; then
            echo "Deleting agent $AGENT_ID..."
            DELETE_RESPONSE=$(curl -s -w "\n%{http_code}" -X DELETE -H "$AUTH_HEADER" "https://${API_ENDPOINT}/v1alpha/$AGENT_ID")
            DEL_CODE=$(echo "$DELETE_RESPONSE" | tail -n 1)
            if [ "$DEL_CODE" -ne 200 ] && [ "$DEL_CODE" -ne 202 ] && [ "$DEL_CODE" -ne 204 ]; then
                echo "Failed to delete agent. HTTP Status: $DEL_CODE. Response: $(echo "$DELETE_RESPONSE" | sed '$d')"
                exit 1
            fi
            echo "Agent deleted."
        else
            echo "No existing agent found with name ${AGENT_DISPLAY_NAME}."
        fi
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
            echo "Deleting Auth ID ${ID}..."
            DELETE_RESPONSE=$(curl -s -w "\n%{http_code}" -X DELETE -H "$AUTH_HEADER" "$AUTH_ID_URL")
            DEL_CODE=$(echo "$DELETE_RESPONSE" | tail -n 1)
            # We don't fail if the delete fails with 404 (doesn't exist)
            if [ "$DEL_CODE" -ne 200 ] && [ "$DEL_CODE" -ne 202 ] && [ "$DEL_CODE" -ne 204 ] && [ "$DEL_CODE" -ne 404 ]; then
                 echo "Failed to delete Auth ID. HTTP Status: $DEL_CODE. Response: $(echo "$DELETE_RESPONSE" | sed '$d')"
                 exit 1
            fi
            echo "Delete command completed for Auth ID ${ID}."
        done
        ;;

    create-auth-ids)
        if [ -z "$AUTH_IDS" ] || [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ] || [ -z "$OAUTH_SCOPES" ] || [ -z "$AUTH_URI_BASE" ] || [ -z "$TOKEN_URI" ]; then
            echo "Error: Missing required parameters for create-auth-ids. Ensure --auth-uri-base and --token-uri are provided."
            exit 1
        fi
        
        ENCODED_SCOPES="${OAUTH_SCOPES// /%20}"
        
        AUTH_URI="${AUTH_URI_BASE}?client_id=${CLIENT_ID}&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Fstatic%2Foauth%2Foauth.html&scope=${ENCODED_SCOPES}&response_type=code&prompt=consent"
        
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
            echo "Creating Auth ID ${ID}..."
            CREATE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST -H "$AUTH_HEADER" -H "Content-Type: application/json" -H "X-Goog-User-Project: ${PROJECT_ID}" "$CREATE_AUTH_URL" -d "$JSON_PAYLOAD")
            CREATE_CODE=$(echo "$CREATE_RESPONSE" | tail -n 1)
            if [ "$CREATE_CODE" -ne 200 ] && [ "$CREATE_CODE" -ne 201 ] && [ "$CREATE_CODE" -ne 202 ]; then
                 echo "Failed to create Auth ID $ID. HTTP Status: $CREATE_CODE. Response: $(echo "$CREATE_RESPONSE" | sed '$d')"
                 exit 1
            fi
            echo "Auth ID $ID creation requested successfully."
        done
        ;;

    register-agent)
        if [ -z "$APP_ID" ] || [ -z "$AGENT_DISPLAY_NAME" ] || [ -z "$AGENT_ENGINE_AGENT_ID" ] || [ -z "$AUTH_IDS" ] || [ -z "$AGENT_ENGINE_LOCATION" ]; then
            echo "Error: Missing required parameters for register-agent."
            exit 1
        fi
        
        PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
        AGENTS_URL="${BASE_URL}/collections/default_collection/engines/${APP_ID}/assistants/default_assistant/agents"
        
        REASONING_ENGINE_PATH="projects/${PROJECT_ID}/locations/${AGENT_ENGINE_LOCATION}/reasoningEngines/${AGENT_ENGINE_AGENT_ID}"
        
        AUTH_ARRAY_JSON=$(echo "$AUTH_IDS" | jq -R -c 'split(",") | map(select(length > 0) | "projects/'"${PROJECT_NUMBER}"'/locations/'"${GE_LOCATION}"'/authorizations/" + .)')
        
        echo "Registering Agent ${AGENT_DISPLAY_NAME} in GE..."
        
        JSON_PAYLOAD=$(jq -n \
            --arg displayName "$AGENT_DISPLAY_NAME" \
            --arg adkResourceId "$REASONING_ENGINE_PATH" \
            --arg description "$GE_AGENT_DESCRIPTION" \
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

        REG_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST -H "$AUTH_HEADER" -H "Content-Type: application/json" -H "X-Goog-User-Project: ${PROJECT_ID}" "$AGENTS_URL" -d "$JSON_PAYLOAD")
        REG_CODE=$(echo "$REG_RESPONSE" | tail -n 1)
        if [ "$REG_CODE" -ne 200 ] && [ "$REG_CODE" -ne 201 ] && [ "$REG_CODE" -ne 202 ]; then
             echo "Failed to register Agent. HTTP Status: $REG_CODE. Response: $(echo "$REG_RESPONSE" | sed '$d')"
             exit 1
        fi
        echo "Agent Registration requested successfully."
        ;;
    
    create-ge-app)
        if [ -z "$APP_ID" ]; then
            echo "Error: --ge-app-id is required for create-ge-app."
            exit 1
        fi
        
        # Determine the description
        DESCRIPTION="${AGENT_DESCRIPTION:-$GE_AGENT_DESCRIPTION}"
        
        # Code adapted from https://docs.cloud.google.com/gemini/enterprise/docs/create-app?hl=en
        echo "Checking if Gemini Enterprise App (Engine: ${APP_ID}) already exists..."
        
        HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
          -H "$AUTH_HEADER" \
          -H "X-Goog-User-Project: $PROJECT_ID" \
          "https://${API_ENDPOINT}/v1/projects/$PROJECT_ID/locations/$GE_LOCATION/collections/default_collection/engines/$APP_ID")
          
        if [ "$HTTP_STATUS" -eq 200 ]; then
            echo "App (Engine) '$APP_ID' already exists. Skipping creation."
        elif [ "$HTTP_STATUS" -eq 404 ]; then
            echo "App (Engine) '$APP_ID' not found. Creating..."
            # Make the REST API call to create the engine
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
            ENG_RES_CODE=$(echo "$ENG_RES" | tail -n 1)
            
            if [ "$ENG_RES_CODE" -ne 200 ] && [ "$ENG_RES_CODE" -ne 201 ] && [ "$ENG_RES_CODE" -ne 202 ]; then
                echo "Failed to create Engine. HTTP Status: $ENG_RES_CODE. Response: $(echo "$ENG_RES" | sed '$d')"
                exit 1
            fi
            echo -e "\nGemini Enterprise App with ID: $APP_ID created successfully."
        else
            echo "Failed to check app status. HTTP Status Code: $HTTP_STATUS"
            exit 1
        fi
        ;;
    
    *)
        echo "Usage: $0 {create-ge-app|delete-agent|delete-auth-ids|create-auth-ids|register-agent} [flags]"
        echo "  create-ge-app flags: --project --ge-app-id [--ge-location]"
        echo "  register-agent flags: --project --app-id --agent-display-name --agent-engine-agent-id --auth-ids --agent-engine-location [--agent-description] [--icon-uri] [--ge-location]"
        exit 1
        ;;
esac
