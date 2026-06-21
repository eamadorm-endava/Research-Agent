# Module Documentation - Atlassian (Jira & Confluence) MCP Server

This module provides a unified integration wrapper for the **Atlassian Jira Cloud REST API (v3)** and **Atlassian Confluence Cloud REST API (v2)**. It exposes standard Model Context Protocol (MCP) tools for AI agents to discover, query, create, and update project data, tickets, Confluence spaces, pages, comments, labels, and attachments.

---

## 1. Directory Structure

All Atlassian component files reside in `mcp_servers/atlassian/`:
```text
mcp_servers/atlassian/
├── app/
│   ├── __init__.py
│   ├── config.py           # Configures JSON secrets and environment variable mapping
│   ├── main.py             # Entry point supporting stdio and streamable-http transports
│   ├── mcp_server.py       # Exposes FastMCP tools and handles logging
│   ├── schemas.py          # Unified Pydantic request and response schemas
│   ├── security.py         # Factory instantiating Atlassian clients
│   ├── gcs_connector.py    # Zero-copy Landing Zone uploader for GCS
│   └── atlassian/          # Client sub-package
│       ├── __init__.py
│       ├── client.py       # Orchestrator delegation wrapper
│       ├── jira_client.py  # Specialised Jira client wrapping issues/projects API
│       └── confluence_client.py # Specialised Confluence client wrapping pages/spaces API
├── tests/                  # Pytest unit and integration tests
└── README.md               # User documentation and CLI Make commands
```

---

## 2. Authentication Flow

Authentication supports both a single JSON-encoded string secret (`ATLASSIAN_CREDENTIALS`) and individual environment variables.

### 2.1 Environmental Mapping
The configuration (`app/config.py`) prioritises individual environment variables over the JSON string to natively integrate with Google Cloud Secret Manager mappings:
*   `JIRA_USER_EMAIL`: User email (e.g. `javier.romero@estrategia52.com`).
*   `JIRA_API_TOKEN`: User API token generated from `id.atlassian.com`.
*   `JIRA_INSTANCE_URL`: Site URL (e.g. `https://davaflow.atlassian.net`).
*   `JIRA_CLOUD_ID`: Cloud identifier UUID.

---

## 3. Supported MCP Tools

The Atlassian MCP server exposes the following tools to the reasoning engine:

### 3.1 Jira Tools
1.  **`list_jira_projects`**: Lists all projects available in Jira.
2.  **`get_jira_project_details`**: Retrieves metadata for a single project.
3.  **`list_jira_project_components`**: Lists components/technologies defined in a project.
4.  **`list_jira_project_categories`**: Lists project categories configured in Jira.
5.  **`search_jira_issues`**: Searches Jira tickets globally using Jira Query Language (JQL), returning `key`, `summary`, `status`, `project`, `priority`, `assignee`, and `updated` fields by default.
6.  **`get_jira_issue_details`**: Retrieves details for a specific ticket including comments.

### 3.2 Confluence Tools
7.  **`list_confluence_spaces`**: Lists Confluence spaces the user has access to.
8.  **`list_confluence_pages`**: Lists Confluence pages, optionally filtered by space ID.
9.  **`search_confluence_pages`**: Searches Confluence pages using Confluence Query Language (CQL).
10. **`get_confluence_page_details`**: Retrieves metadata of a single Confluence page.
11. **`read_confluence_page`**: Retrieves page content, converts HTML/storage format to Markdown, streams it to the **GCS Landing Zone**, and returns the GCS URI with the `inject_file_data: True` flag.
12. **`create_confluence_page`**: Creates a new page in Confluence.
13. **`update_confluence_page`**: Updates an existing Confluence page (requires version number incrementation).
14. **`list_confluence_page_attachments`**: Lists files attached to a specific page.
15. **`get_confluence_attachment_details`**: Retrieves metadata of a specific attachment.
16. **`list_confluence_page_comments`**: Lists footer comments for a specific page.
17. **`create_confluence_page_comment`**: Creates a footer comment on a specific page.
18. **`list_confluence_page_labels`**: Lists labels/tags associated with a page.

---

## 4. GCS Landing Zone Ingestion

When reading a Confluence page using `read_confluence_page`:
1.  The storage HTML body is retrieved from the Confluence API.
2.  The content is converted to clean Markdown format.
3.  The text stream is uploaded dynamically to Google Cloud Storage under:
    `gs://{LANDING_ZONE_BUCKET}/{app_name}/{user_id}/{session_id}/atlassian-{timestamp}-{safe_title}.md`
4.  The uploader updates the GCS IAM policy to grant the user (`user_id`) read access to their folder prefix (`uploader-folder-access` condition). 
    *   **Graceful Fallback**: If setting the IAM policy fails (e.g., due to a `412 Precondition Failed` error when GCP Organization Policies restrict adding external email domains to project IAM policies), the error is caught and logged as a warning, and the ingestion process continues successfully.
5.  The tool returns the GCS URI and instructs the agent plugin to load the content directly into the prompt context.
