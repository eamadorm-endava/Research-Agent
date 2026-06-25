# Microsoft Entra ID Setup for Data Connectors

To allow the AI Agent (via Vertex AI Agent Engine or a custom MCP Server) to connect and read data from Microsoft services (OneDrive, SharePoint, Outlook, Teams), you must register an OAuth 2.0 application in Microsoft Entra ID.

> [!NOTE]
> **A single App Registration is all that is needed.** Because Microsoft Graph acts as the unified API gateway for Microsoft 365, you can bundle all the required permissions (scopes) for OneDrive, SharePoint, Outlook, and Teams into this one application.

Follow these steps to configure the application, generate credentials, and grant the necessary API permissions.

## 1. Register the Application

1. Go to the [Microsoft Entra admin center](https://entra.microsoft.com/) and log in with your administrator account.
2. Navigate to **Identity** > **Applications** > **App registrations**.
3. Click on **New registration**.
4. **Name**: Provide a descriptive name for your application (e.g., `Research-Agent-Connectors`).
5. **Supported account types**: Select **Accounts in this organizational directory only (Single tenant)**.
6. Click **Register**.

## 2. Generate a Client Secret

1. Under the **Manage** menu on the left, click **Certificates & secrets**.
2. Go to the **Client secrets** tab and click **New client secret**.
3. Add a description (e.g., `Agent MCP Secret`).
4. **Expires**: Select **1 year** (recommended) or at least **6 months**.
5. Click **Add**.
6. **CRITICAL**: Copy the **Secret Value** immediately. This value will be hidden once you navigate away from this page. This is your `CLIENT_SECRET`.

## 3. Define API Permissions (Scopes)

1. Under the **Manage** menu, click **API permissions**.
2. Click **Add a permission** > **Microsoft Graph** > **Delegated permissions**.
3. Search for and check the following permissions:
   - `Files.Read.All` (Include the services that will be used, like SharePoint, OneDrive, Outlook)
   - `Sites.Read.All`
   - `User.Read` (to correctly authenticate to the MCPs)
   - `offline_access`
   - `email`
   - `Mail.Read`
   - `Mail.Read.Shared`
4. Once all the required permissions are checked, click **Add permissions** at the bottom.

## 4. Grant Admin Consent

To prevent users from being blocked by corporate policies:
1. On the **API permissions** page, click the **Grant admin consent for [Your Tenant Name]** button located above the permissions list.
2. Confirm the action. Make sure to grant admin consent on all of them (the status column should show a green checkmark).

## 5. Configure Authentication (Redirect URLs)

1. Under the **Manage** menu, click **Authentication**.
2. Click **Add a platform** and select **Web**.
3. Include the following Redirect URLs:
   - `http://localhost:8000/dev-ui/` -> For local testing with ADK
   - `https://vertexaisearch.cloud.google.com/static/oauth/oauth.html` -> For GE
   - `https://vertexaisearch.cloud.google.com/oauth-redirect` -> For GE
4. Click **Configure** and save the changes.

## 6. Mandatory: Enterprise Applications Admin Consent

1. Navigate to **Identity** > **Applications** > **Enterprise applications**.
2. Search for and select the application you just registered.
3. In the left menu, under **Security**, click on **Permissions**.
4. Click the button to **Grant admin consent for [Your Tenant Name]**.

## 7. Store Credentials

> [!IMPORTANT]
> Store the **CLIENT_ID**, **TENANT_ID**, and **CLIENT_SECRET** securely. These will be used in the GE auth resources and local `.env` files.

## 8. Gemini Enterprise Auth Configuration Note

When creating the Auth ID in Gemini Enterprise for this Microsoft Entra application, ensure that you set the prompt parameter to `select_account` (as defined in the CI/CD pipelines) instead of the default `consent`.

> **Why?** If the prompt is set to `consent`, Microsoft Entra ID will attempt to force the user to re-consent to the permissions every time they log in. Since these are enterprise-level scopes, a regular user will hit a "Needs admin approval" error screen and get blocked. By granting Admin Consent globally (Step 6) and using `prompt=select_account`, the user simply picks their Microsoft account and the authentication succeeds silently without asking for consent again.
