#!/bin/sh
# Existing deployers have projectIamAdmin; reconcile the two UI-specific roles.
set -eu
project_id="$1"
service_account_name="$2"
for role in roles/iam.roleAdmin roles/iap.admin; do
  gcloud projects add-iam-policy-binding "$project_id" \
    --member="serviceAccount:${service_account_name}@${project_id}.iam.gserviceaccount.com" \
    --role="$role" --condition=None --quiet --format=none
done
