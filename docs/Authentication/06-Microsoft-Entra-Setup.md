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
6. **Redirect URI**: Select **Web** from the dropdown and add the following URLs. (You can add the first one here, and the rest later in the Authentication menu):
   - `https://vertexaisearch.cloud.google.com/static/oauth/oauth.html`
   - `https://vertexaisearch.cloud.google.com/oauth-redirect`
   - `http://localhost:8000/dev-ui/`
7. Click **Register**.

## 2. Gather Credentials

Once the application is registered, you will be directed to its overview page.
1. Copy the **Application (client) ID**. This is your `Client ID`.
2. Copy the **Directory (tenant) ID**. This is your `Tenant ID`.

## 3. Generate a Client Secret

1. Under the **Manage** menu on the left, click **Certificates & secrets**.
2. Go to the **Client secrets** tab and click **New client secret**.
3. Add a description (e.g., `Agent MCP Secret`) and select an expiration period.
4. Click **Add**.
5. **CRITICAL**: Copy the **Secret Value** immediately. This value will be hidden once you navigate away from this page. This is your `Client Secret`.

## 4. Define API Permissions (Scopes)

You need to grant **Delegated permissions** (since the agent acts on behalf of the user via an OAuth flow) to read files and content from the various Microsoft services.

1. Under the **Manage** menu, click **API permissions**.
2. Click **Add a permission** > **Microsoft Graph** > **Delegated permissions**.
3. Search for and check the following permissions based on the connectors you want to enable:

### General (Mandatory)
- `offline_access`: Required to grant Google / the Agent a refresh token. This ensures the connection stays active without requiring the user to constantly re-authenticate.
- `User.Read`: Basic profile reading required for token validation.

### OneDrive & SharePoint
*(Note: Files shared in Microsoft Teams are physically stored in SharePoint and OneDrive. These permissions cover those files as well.)*
- `Files.Read.All`: Allows reading all files the signed-in user has access to.
- `Sites.Read.All`: Allows reading all SharePoint site items and lists the signed-in user has access to.

### Outlook
- `Mail.Read`: Allows reading the user's email messages.
- `Mail.Read.Shared`: *(Optional)* Allows reading email in shared folders or delegated mailboxes if your agent needs that capability.

### Microsoft Teams
- `Team.ReadBasic.All`: Allows the application to list the Teams the user is a member of.
- `Channel.ReadBasic.All`: Allows the application to list the channels within those Teams.
- `ChannelMessage.Read.All`: Allows reading messages in channels the user has access to.
- `Chat.Read`: Allows reading 1-on-1 and group chat messages.

4. Once all the required permissions are checked, click **Add permissions** at the bottom.

## 5. Grant Admin Consent

To prevent users from being blocked by corporate policies that require administrator approval for these specific scopes:
1. On the **API permissions** page, click the **Grant admin consent for [Your Tenant Name]** button located above the permissions list.
2. Confirm the action. The status column for all permissions should change to a green checkmark indicating "Granted".


## 6. Configure Environment Variables

Use Microsoft-wide auth variable names so one Microsoft Graph OAuth connection can be reused by multiple Microsoft MCP servers:

```env
GEMINI_MICROSOFT_AUTH_ID=your-gemini-enterprise-microsoft-auth-resource-id
MICROSOFT_TENANT_ID=your-tenant-id-or-organizations
MICROSOFT_GRAPH_OAUTH_SCOPES=["User.Read", "Files.Read.All", "Sites.Read.All", "offline_access"]
MICROSOFT_OAUTH_CLIENT_ID=your-entra-application-client-id
MICROSOFT_OAUTH_CLIENT_SECRET=your-entra-client-secret
MICROSOFT_OAUTH_REDIRECT_URI=http://localhost:8000/dev-ui
```

Legacy SharePoint-specific aliases such as `GEMINI_SHAREPOINT_AUTH_ID`, `SHAREPOINT_AUTH_ID`, `SHAREPOINT_OAUTH_SCOPES`, and `SHAREPOINT_TENANT_ID` are still accepted for compatibility, but new Microsoft MCP servers should use the Microsoft-wide names above.

---

> [!IMPORTANT]
> Store the **Client ID**, **Client Secret**, and **Tenant ID** securely (e.g., inside Google Secret Manager or your local `.env` file). These values must not be committed to version control and will be passed to your `config.py` as environment variables for the MCP Server.
