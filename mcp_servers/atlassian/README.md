# Atlassian (Jira & Confluence) MCP Server

This MCP server provides a unified integration wrapper for the **Atlassian Jira Cloud REST API (v3)** and **Atlassian Confluence REST API (v2)**. It is designed to allow AI agents to extract and summarize useful project and ticket information, map technologies used via components, classify clients/domains via categories, and query Confluence spaces, pages, comments, labels, and attachments without mutating Atlassian content.

---

## Architectural Highlights

- **Standardized Schema Contracts**: Built exclusively using Pydantic `BaseModel`. All exposed tools receive well-defined `Request` objects and return consistent `Response` objects.
- **Traceability (Parameter Echoing)**: Response schemas dynamically inherit from their corresponding Requests and a common `BaseResponse`. Every tool returns the `execution_status` ("success" or "error"), the `execution_message`, and echoes back the original input parameters.
- **Graceful Error Handling**: Catch and handle exceptions gracefully, returning standard status codes and structured errors in responses. Specifically, GCS Landing Zone IAM policy binding failures (e.g. 412 errors due to organizational constraints on external domains) are caught and logged as warnings, ensuring that document ingestion still succeeds.
- **Unified Observability**: Leveraging `loguru`, the server implements tiered logging: `DEBUG` for internal queries and transformations, `INFO` for unified routing boundaries, and `WARNING`/`ERROR` for API exceptions.

---

## Core Capabilities
 
The server exposes read-only tools to the calling agent:

### 1. Jira Tools
1. **`list_jira_projects`**: Lists all projects available in Jira. Useful for overall project discovery.
2. **`get_jira_project_details`**: Retrieves details of a single Jira project, including category and lead.
3. **`list_jira_project_components`**: Lists components of a project, which represent the technical stacks, languages, or frameworks used.
4. **`list_jira_project_categories`**: Lists project categories configured in Jira, representing different clients or domains.
5. **`search_jira_issues`**: Searches Jira tickets globally using Jira Query Language (JQL), supporting pagination.
6. **`get_jira_issue_details`**: Retrieves details for a specific ticket, including description, status, and comments.

### 2. Confluence Tools
7. **`list_confluence_spaces`**: Lists Confluence spaces the user has access to.
8. **`list_confluence_pages`**: Lists pages, optionally filtered by space ID.
9. **`search_confluence_pages`**: Searches pages globally using Confluence Query Language (CQL).
10. **`get_confluence_page_details`**: Retrieves metadata of a single page.
11. **`read_confluence_page`**: Reads page content, parses HTML body to Markdown, streams it to the GCS Landing Zone, and returns the GCS URI.
12. **`list_confluence_page_attachments`**: Lists files attached to a page.
13. **`get_confluence_attachment_details`**: Retrieves metadata for a specific attachment.
14. **`list_confluence_page_comments`**: Lists footer comments for a page.
15. **`list_confluence_page_labels`**: Lists labels/tags associated with a page.

---

## Authentication Configuration

The preferred deployment path uses **Atlassian OAuth 2.0 / 3LO**. The user is sent to Atlassian's authorization endpoint; if the Atlassian organization is configured with Microsoft SSO, the visible sign-in step is Microsoft SSO, but the resulting delegated token is still an Atlassian access token.

Required Agent/Gemini Enterprise variables:

```bash
ATLASSIAN_OAUTH_CLIENT_ID=<oauth-2-3lo-client-id>
ATLASSIAN_OAUTH_CLIENT_SECRET=<oauth-2-3lo-client-secret>
GEMINI_ATLASSIAN_AUTH_ID=atlassian-authentication
```

The OAuth app must use the Atlassian callback URL registered for Gemini Enterprise and include the scopes used by this MCP server: Jira read scopes, Confluence read scopes, and `offline_access` for refresh support.

The MCP server validates incoming bearer tokens through `https://api.atlassian.com/oauth/token/accessible-resources` and then calls Jira and Confluence through the `https://api.atlassian.com/ex/.../{cloudId}` gateway. For multi-site tenants, set `JIRA_CLOUD_ID` to force a specific Atlassian site; otherwise, the first Jira/Confluence-scoped accessible resource is selected.

Legacy static API-token credentials are still supported as a local fallback when no MCP auth context is present. The expected JSON format is:

```json
{
  "JIRA_USER_EMAIL": "user@example.com",
  "JIRA_API_TOKEN": "your-atlassian-api-token",
  "JIRA_INSTANCE_URL": "https://your-instance.atlassian.net",
  "JIRA_CLOUD_ID": "your-cloud-id"
}
```

Locally, this JSON can be provided via the `ATLASSIAN_CREDENTIALS` environment variable in `mcp_servers/atlassian/.env`.

---

## Quick Start & Make Commands

The project manages continuous integration and local development through `uv` and the global repository `Makefile`.

### 1. Installation

Sync the exact dependencies for the Atlassian server securely using your `uv.lock`:
```bash
uv sync --group mcp_atlassian
```

### 2. Running Locally

The Atlassian MCP runs locally on port `8085`:
```bash
make run-atlassian-mcp-locally
```

### 3. Running Tests & QA

Verify the entire pipeline (Pre-commit, Pytest, and Docker Build):
```bash
make verify-atlassian-ci
```

To run smoke tests manually against a running local instance:
```bash
make run-atlassian-mcp-smoke
```
