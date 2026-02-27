#!/bin/bash
# scripts/bootstrap-terraform.sh

set -e

# --- Configuration ---
PROJECT_ID="p-dev-gce-60pf"
SA_NAME="terraform-sa-gemini-project"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
DEVELOPER_GROUP_EMAIL="research-agent-dev-test@endava.com" # Update with your email or group

echo "Starting bootstrap for project: $PROJECT_ID"

# 1. Create the Service Account
if ! gcloud iam service-accounts describe $SA_EMAIL --project=$PROJECT_ID > /dev/null 2>&1; then
    echo "Creating Service Account: $SA_NAME..."
    gcloud iam service-accounts create $SA_NAME \
        --display-name="Terraform Management Account" \
        --project=$PROJECT_ID
    
    echo "Waiting for identity propagation (15s)..."
    sleep 15  # <--- THIS IS THE FIX
else
    echo "Service Account $SA_NAME already exists."
fi

# 2. Assign Project-Level Roles to the SA
echo "Assigning infrastructure roles to $SA_NAME..."
ROLES=(
    "roles/serviceusage.serviceUsageAdmin"
    "roles/iam.serviceAccountAdmin"
    "roles/resourcemanager.projectIamAdmin"
)

for ROLE in "${ROLES[@]}"; do
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:$SA_EMAIL" \
        --role="$ROLE" \
        --condition=None
done

# 3. Grant Developer Impersonation (Token Creator)
echo "Granting $DEVELOPER_GROUP_EMAIL the ability to impersonate $SA_NAME..."
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
    --member="group:$DEVELOPER_GROUP_EMAIL" \
    --role="roles/iam.serviceAccountTokenCreator" \
    --project=$PROJECT_ID

# 4. THE 2ND GEN FIX: Grant Cloud Build SYSTEM AGENT permissions
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
CB_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-cloudbuild.iam.gserviceaccount.com"

echo "Applying 2nd Gen 'System-to-SA' bridge permissions..."

# 4.1. Grant System Agent 'Service Account User' on your custom SA
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
    --member="serviceAccount:$CB_SERVICE_AGENT" \
    --role="roles/iam.serviceAccountUser" \
    --project=$PROJECT_ID \
    --condition=None

# 4.2. Grant System Agent its core role (re-asserting)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$CB_SERVICE_AGENT" \
    --role="roles/cloudbuild.serviceAgent" \
    --condition=None

# 4.3. Ensure logging for the custom SA
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/logging.logWriter" \
    --condition=None


# 1. Grant the SA the Service Agent role at the project level
echo "Granting Service Agent role to custom SA (Required for 2nd Gen)..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/cloudbuild.serviceAgent" \
    --condition=None

# 2. Grant the Cloud Build 'Internal System' permission to use your SA
# (Using your project number 753988132239 from the error message)
echo "Granting System Agent permission to act as your custom SA..."
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
    --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-cloudbuild.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser" \
    --project="$PROJECT_ID" \
    --condition=None

# 3. CRITICAL: Add the 'Cloud Build Service Account' role
# This is a specific role (roles/cloudbuild.builds.builder) that permits 
# the SA to actually execute a 'build' resource in the project.
echo "Granting builder role..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/cloudbuild.builds.builder" \
    --condition=None

echo "Waiting for identity propagation (15s)..."
sleep 15  # <--- THIS IS THE FIX

# 5. Enable Cloud Build API (Required for trigger creation)
echo "Ensuring Cloud Build API is enabled..."
gcloud services enable cloudbuild.googleapis.com --project=$PROJECT_ID

# 6. Create Cloud Build Triggers
# GitHub Configuration
REPO_NAME="Research-Agent"
REPO_OWNER="eamadorm-endava"
BRANCH_NAME="" # Your specific development branch

echo "Creating Cloud Build Triggers..."

# Function to create triggers
create_trigger() {
    local NAME=$1
    local TYPE=$2
    local DIR=$3
    local CONFIG=$4
    local REGION="us-central1"
    local CONNECTION_NAME="eamadorm-github"
    
    # Use the PROJECT_NUMBER from your error (753988132239)
    # The path for Cloud Build v2 is /connections/NAME/repositories/REPO_NAME
    local REPO_PATH="projects/$PROJECT_NUMBER/locations/$REGION/connections/$CONNECTION_NAME/repositories/eamadorm-endava-Research-Agent"

    if [[ "$TYPE" == "pr" ]]; then
        echo "Creating 2nd Gen PR Trigger: $NAME"
        # Note: We use the 'github' flag for v2 connections
        gcloud alpha builds triggers create github \
            --name="$NAME" \
            --project="$PROJECT_ID" \
            --region="$REGION" \
            --repository="$REPO_PATH" \
            --pull-request-pattern="^main$" \
            --build-config="$CONFIG" \
            --included-files="$DIR/**" \
            --service-account="projects/$PROJECT_ID/serviceAccounts/$SA_EMAIL"
    else
        echo "Creating 2nd Gen Push Trigger: $NAME"
        gcloud alpha builds triggers create github \
            --name="$NAME" \
            --project="$PROJECT_ID" \
            --region="$REGION" \
            --repository="$REPO_PATH" \
            --branch-pattern="^main$" \
            --build-config="$CONFIG" \
            --included-files="$DIR/**" \
            --service-account="projects/$PROJECT_ID/serviceAccounts/$SA_EMAIL"
    fi
}

# --- API Services Triggers ---
# CI (Plan) on Pull Request
create_trigger "api-services-plan" "pr" "terraform/api-service" "terraform/api-service/api-service-cloud-build-ci.yaml"
# CD (Apply) on Push/Merge
create_trigger "api-services-apply" "push" "terraform/api-service" "terraform/api-service/api-service-cloud-build-cd.yaml"

# --- Service Accounts Triggers ---
# CI (Plan) on Pull Request
create_trigger "service-accounts-plan" "pr" "terraform/service-accounts" "terraform/service-accounts/service-accounts-cloud-build-ci.yaml"
# CD (Apply) on Push/Merge
create_trigger "service-accounts-apply" "push" "terraform/service-accounts" "terraform/service-accounts/service-accounts-cloud-build-cd.yaml"

echo "Triggers created successfully!"
echo "Bootstrap complete!"
echo "To use this locally, run: gcloud auth application-default login --impersonate-service-account=$SA_EMAIL"