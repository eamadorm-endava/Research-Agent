#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# Gemini Enterprise Resource Provisioning Script (Stage 1)
# -----------------------------------------------------------------------------
# Enables necessary APIs and provisions the Gemini Enterprise App (Engine).
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROJECT_ID=""
GE_LOCATION="global"
GE_APP_ID=""
GE_APP_NAME_SUFFIX="osiris-app"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --project) PROJECT_ID="$2"; shift ;;
        --ge-location) GE_LOCATION="$2"; shift ;;
        --ge-app-id|--app-id) GE_APP_ID="$2"; shift ;;
        --ge-app-name-suffix) GE_APP_NAME_SUFFIX="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$PROJECT_ID" ]; then
    echo "Error: --project is required."
    exit 1
fi

if [ -z "$GE_APP_ID" ]; then
    GE_APP_ID="${PROJECT_ID}-${GE_LOCATION}-${GE_APP_NAME_SUFFIX}"
fi

echo "================================================================="
echo "GEMINI ENTERPRISE PROVISIONING"
echo "================================================================="
echo "Project: $PROJECT_ID"
echo "Location: $GE_LOCATION"
echo "App / Engine ID: $GE_APP_ID"
echo "-----------------------------------------------------------------"

echo "Ensuring required GCP APIs are enabled (discoveryengine, dialogflow)..."
gcloud services enable discoveryengine.googleapis.com dialogflow.googleapis.com --project="$PROJECT_ID"

echo "Provisioning Gemini Enterprise App..."
bash "$SCRIPT_DIR/ge_manager.sh" create-ge-app \
    --project "$PROJECT_ID" \
    --ge-location "$GE_LOCATION" \
    --app-id "$GE_APP_ID"

echo "================================================================="
echo "Gemini Enterprise App setup complete."
echo "================================================================="
