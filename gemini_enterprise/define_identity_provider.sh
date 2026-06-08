#!/bin/bash
# Script to configure Microsoft Entra ID (Azure AD) as an external identity provider
# using Google Cloud Workforce Identity Federation.
#
# Prerequisites:
# - An active Google Cloud Organization (Workforce Pools exist at the Org level)
# - Microsoft Entra ID Tenant ID and Client ID for your registered application.

set -e

ORGANIZATION_ID=${1:-"YOUR_ORG_ID"}
POOL_ID=${2:-"my-entra-id-pool"}
PROVIDER_ID=${3:-"my-entra-id-provider"}
ENTRA_TENANT_ID=${4:-"YOUR_ENTRA_TENANT_ID"}
ENTRA_CLIENT_ID=${5:-"YOUR_ENTRA_CLIENT_ID"}

echo "Creating Workforce Identity Pool: $POOL_ID in organization $ORGANIZATION_ID"
gcloud iam workforce-pools create "$POOL_ID" \
    --organization="$ORGANIZATION_ID" \
    --location="global" \
    --description="Identity Pool for Microsoft Entra ID users" \
    --display-name="Entra ID Pool"

echo -e "\nCreating OIDC Identity Provider: $PROVIDER_ID in pool $POOL_ID"
gcloud iam workforce-pools providers create-oidc "$PROVIDER_ID" \
    --workforce-pool="$POOL_ID" \
    --location="global" \
    --display-name="Entra ID Provider" \
    --issuer-uri="https://login.microsoftonline.com/$ENTRA_TENANT_ID/v2.0" \
    --client-id="$ENTRA_CLIENT_ID" \
    --attribute-mapping="google.subject=assertion.sub,google.groups=assertion.groups,google.display_name=assertion.name,attribute.user_principal_name=assertion.preferred_username"

echo -e "\nWorkforce Identity Provider configured successfully."
