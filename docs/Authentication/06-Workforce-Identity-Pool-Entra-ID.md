# Workforce Identity Pool & Microsoft Entra ID Integration

This document explains what a Workforce Identity Pool is in Google Cloud, and provides a guide on how to configure it using the Google Cloud CLI (`gcloud`) specifically for Microsoft Entra ID (formerly Azure AD).

## What is a Workforce Identity Pool?

A **Workforce Identity Pool** acts as a "trust bridge" between Google Cloud and an external Identity Provider (IdP) like Microsoft Entra ID, Okta, or Ping Identity.

Instead of creating separate Google Workspace or Cloud Identity accounts for your employees to access Google Cloud resources (such as a Gemini Enterprise App or Vertex AI Agent), you can use a Workforce Identity Pool. It allows you to say: *"Trust the authentication that happens in my external directory."*

**How it works:**
1. A user authenticates to their company portal using their Microsoft Entra ID credentials.
2. Entra ID generates a secure token (OIDC or SAML).
3. The token is passed to the Google Cloud Workforce Identity Pool.
4. The pool validates the token, applies attribute mapping rules, and issues short-lived Google Cloud credentials.
5. The user can now access Google Cloud resources based on their assigned IAM roles, without needing a dedicated Google account.

---

## Setting up Workforce Identity Federation with Entra ID using CLI

This guide demonstrates how to set up an OIDC connection between Microsoft Entra ID and a Google Cloud Workforce Identity Pool using the `gcloud` CLI.

### Prerequisites

1. **Google Cloud Organization ID:** Workforce Identity Pools are created at the organization level, not the project level.
2. **Microsoft Entra ID Application:** You must register an application in your Microsoft Entra ID tenant to obtain:
   - `Client ID`
   - `Issuer URI` (e.g., `https://login.microsoftonline.com/TENANT_ID/v2.0`)

### Step 1: Create the Workforce Identity Pool

The pool acts as the container for your external identities. Create it at your organization level:

```bash
gcloud iam workforce-pools create my-entra-id-pool \
    --organization="YOUR_ORGANIZATION_ID" \
    --location="global" \
    --description="Identity Pool for Microsoft Entra ID users" \
    --display-name="Entra ID Pool"
```

### Step 2: Add Entra ID as an Identity Provider

Once the pool is created, you need to add Microsoft Entra ID as a trusted provider within that pool. This is where you configure the OIDC connection details.

```bash
gcloud iam workforce-pools providers create-oidc my-entra-id-provider \
    --workforce-pool="my-entra-id-pool" \
    --location="global" \
    --display-name="Entra ID Provider" \
    --issuer-uri="https://login.microsoftonline.com/YOUR_ENTRA_TENANT_ID/v2.0" \
    --client-id="YOUR_ENTRA_CLIENT_ID" \
    --attribute-mapping="google.subject=assertion.sub,google.groups=assertion.groups,google.display_name=assertion.name,attribute.user_principal_name=assertion.preferred_username"
```

#### Understanding Attribute Mapping
The `--attribute-mapping` flag translates Microsoft Entra ID token claims into Google Cloud identity attributes. 
- `google.subject`: A required mapping that uniquely identifies the user.
- `google.groups`: Maps Entra ID security groups to Google Cloud, which is crucial for enforcing document-level access controls in tools like Gemini Enterprise.
- `attribute.user_principal_name`: A custom attribute mapped to the user's email/UPN.

### Step 3: Grant IAM Permissions

Once the pool and provider are set up, users from Entra ID have no access by default. You must grant them IAM roles to interact with Google Cloud resources.

To grant access to a specific group from Entra ID (e.g., to allow them to query a Discovery Engine App), you assign an IAM role to the `principalSet` representing that group:

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --role="roles/discoveryengine.viewer" \
    --member="principalSet://iam.googleapis.com/locations/global/workforcePools/my-entra-id-pool/group/ENTRA_GROUP_ID"
```

To grant access to an individual user:

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --role="roles/discoveryengine.viewer" \
    --member="principal://iam.googleapis.com/locations/global/workforcePools/my-entra-id-pool/subject/USER_SUBJECT_ID"
```

---

## Important Considerations for Gemini Enterprise

When configuring a Gemini Enterprise / Discovery Engine App that searches Microsoft data sources (like SharePoint or OneDrive), **you must map Microsoft Entra ID groups**. 

The search engine uses these groups to enforce Document Level Security (DLS). If a user searches for documents, the engine verifies their Workforce Identity Federation group memberships to ensure they only see documents they are authorized to view in SharePoint/OneDrive.
