#!/bin/bash
# scripts/bootstrap-terraform.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- Configuration ---

#service accounts and IAM roles
PROJECT_ID="p-dev-gce-60pf"
SA_NAME="terraform-sa-gemini-project"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
USER_EMAIL="davidalejandro.sanchezarias@endava.com"
DEVELOPER_GROUP_EMAIL="gcu_latam_team_devs@endava.com" # Update with your email or group

#bucket
BUCKET_NAME="${PROJECT_ID}-terraform-state" #GCS Bucket to storage terraform state
LOCATION="us-central1"

# GitHub
REPO_NAME="Research-Agent"
REPO_OWNER="eamadorm-endava"
BRANCH_NAME="" # Your specific development branch
GITHUB_REGION="us-central1"
GITHUB_CONNECTION_NAME="eamadorm-github"
APPLY_SHARED_RESOURCES="${APPLY_SHARED_RESOURCES:-true}"

echo "Starting bootstrap for project: $PROJECT_ID"

# 1. Create the Service Account
if ! gcloud iam service-accounts describe $SA_EMAIL --project=$PROJECT_ID > /dev/null 2>&1; then
    echo "Creating Service Account: $SA_NAME..."
    gcloud iam service-accounts create $SA_NAME \
        --display-name="Terraform Management Account" \
        --project=$PROJECT_ID
    
    echo "Waiting for identity propagation (15s)..."
    sleep 15
else
    echo "Service Account $SA_NAME already exists."
fi

# 2. Assign Project-Level Roles to the SA
echo "Assigning infrastructure roles to $SA_NAME..."
ROLES=(
    "roles/serviceusage.serviceUsageAdmin"
    "roles/iam.serviceAccountAdmin"
    "roles/resourcemanager.projectIamAdmin"
    "roles/artifactregistry.admin"
    "roles/run.admin"
    "roles/iam.serviceAccountUser"
    "roles/aiplatform.admin"
    "roles/secretmanager.secretAccessor"
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
sleep 15

# 5. Enable Cloud Build API (Required for trigger creation)
echo "Ensuring Cloud Build API is enabled..."
gcloud services enable cloudbuild.googleapis.com --project=$PROJECT_ID

# 6. --- Create GCS Bucket for Terraform State ---
if ! gcloud storage buckets describe gs://$BUCKET_NAME > /dev/null 2>&1; then
    echo "Creating GCS bucket for Terraform state: $BUCKET_NAME..."
    gcloud storage buckets create gs://$BUCKET_NAME \
        --project=$PROJECT_ID \
        --location=$LOCATION \
        --uniform-bucket-level-access

    echo "Enabling versioning on bucket..."
    gcloud storage buckets update gs://$BUCKET_NAME --versioning
else
    echo "Bucket $BUCKET_NAME already exists."
fi

# 6.2 Grant the Service Account permissions on the bucket
echo "Granting $SA_NAME Storage Object Admin on the state bucket..."
gcloud storage buckets add-iam-policy-binding gs://$BUCKET_NAME \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/storage.objectAdmin"

# 7. Give impersonation in Terraform sa to your user
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --member="user:$USER_EMAIL" \
  --role="roles/iam.serviceAccountUser" \
  --project="$PROJECT_ID"

# 8. One-time shared resources apply (Artifact Registry owner state)
if [[ "$APPLY_SHARED_RESOURCES" == "true" ]]; then
    echo "Applying one-time shared resources (Artifact Registry)..."
    pushd "$REPO_ROOT/terraform/shared_resources" >/dev/null
    terraform init -reconfigure \
        -backend-config="bucket=${BUCKET_NAME}" \
        -backend-config="prefix=terraform/state/shared-resources"
    terraform plan
    terraform apply -auto-approve
    popd >/dev/null
else
    echo "Skipping shared_resources apply (APPLY_SHARED_RESOURCES=${APPLY_SHARED_RESOURCES})."
fi

# 9. Create Cloud Build Triggers
echo "Executing trigger setup (cicd_triggers_creation.sh)..."
bash "$SCRIPT_DIR/cicd_triggers_creation.sh"

echo "Triggers created successfully!"
echo "Bootstrap complete!"
echo "To use this locally, run: gcloud auth application-default login --impersonate-service-account=$SA_EMAIL"