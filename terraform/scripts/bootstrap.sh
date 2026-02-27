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

# 4. Grant Cloud Build Impersonation
# Get the Cloud Build SA email automatically
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

echo "Granting Cloud Build ($CLOUDBUILD_SA) permission to act as $SA_NAME..."
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
    --member="serviceAccount:$CLOUDBUILD_SA" \
    --role="roles/iam.serviceAccountTokenCreator" \
    --project=$PROJECT_ID

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
    local TYPE=$2   # "pr" or "push"
    local DIR=$3    
    local CONFIG=$4 

    if [[ "$TYPE" == "pr" ]]; then
        echo "Creating PR Trigger: $NAME (Source: feature/** -> Destination: main)"
        gcloud beta builds triggers create github \
            --name="$NAME" \
            --project="$PROJECT_ID" \
            --repo-name="$REPO_NAME" \
            --repo-owner="$REPO_OWNER" \
            --pull-request-pattern="^main$" \
            --comment-control="COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY" \
            --build-config="$CONFIG" \
            --included-files="$DIR/**"
            # Note: Cloud Build automatically triggers PRs from any source branch 
            # targeting the pattern in --pull-request-pattern.
    else
        echo "Creating Push Trigger: $NAME (Branch: main)"
        gcloud beta builds triggers create github \
            --name="$NAME" \
            --project="$PROJECT_ID" \
            --repo-name="$REPO_NAME" \
            --repo-owner="$REPO_OWNER" \
            --branch-pattern="^main$" \
            --build-config="$CONFIG" \
            --included-files="$DIR/**"
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