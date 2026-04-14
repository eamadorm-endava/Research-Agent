# Google Drive MCP Connector Scopes Documentation

## Purpose

This document describes the OAuth scopes required by the Google Drive MCP connector, how each scope is used by the connector tools, how scope validation works, and how to enable the scopes in Google Cloud and in the local agent configuration.

This documentation is written for the current MCP-based Google Drive connector architecture, where:

- the agent connects to the Drive MCP server
- the Drive MCP server calls the Google Drive API
- OAuth tokens are validated against the scopes required by each tool operation

---

## Architecture Context

There are two distinct authentication layers in this integration:

1. Agent to MCP server authentication
   - This is the authentication required for the agent to call the MCP server.
   - Depending on deployment, this may use:
     - no auth for local development
     - ID token or bearer token for Cloud Run
     - OAuth-based MCP authentication

2. MCP server to Google Drive API authorization
   - This is the authorization that determines what the connector can do in the user's Google Drive.
   - This is where the Google Drive OAuth scopes described in this document apply.

The scopes below are about Google Drive access, not generic MCP transport authentication.

---

## Scope Inventory

The connector currently recognizes and or uses the following Google scopes.

### 1. `https://www.googleapis.com/auth/drive`

**Description**  
Full read and write access to all files in the user's Google Drive.

**What it allows**
- List files and folders anywhere in the user's Drive
- Search files and folders anywhere in the user's Drive
- Read metadata and file contents
- Create files and folders
- Move files and folders
- Rename files and folders
- Update parent relationships
- Upload binary files, including PDFs
- Create Google Docs
- Access files that were not created by the application

**Why it matters**  
This is the broadest Drive scope used by the connector and is the most practical scope when the connector is expected to manage the user's Drive workspace, not only files created by the application.

**Current practical usage**  
This scope is the recommended scope for:
- local end-to-end testing
- advanced Drive management features
- future production flows where the agent needs to organize existing user content

**Tools that can rely on it**
- `list_files`
- `get_file_text`
- `create_file`
- `create_folder`
- `move_file`
- `rename_file`
- `upload_pdf`
- `create_google_doc`

---

### 2. `https://www.googleapis.com/auth/drive.readonly`

**Description**  
Read-only access to all files in the user's Google Drive.

**What it allows**
- List files and folders
- Read metadata
- Download and export content
- Extract text from supported file types

**What it does not allow**
- Create files
- Create folders
- Rename items
- Move items
- Modify file contents
- Upload PDFs
- Create Google Docs

**Why it matters**  
This scope is useful if the connector is intentionally restricted to discovery and retrieval use cases.

**Tools that use or conceptually map to it**
- `list_files`
- `get_file_text`

**Note**  
If the access token already contains the broader `drive` scope, the connector can treat it as satisfying `drive.readonly`.

---

### 3. `https://www.googleapis.com/auth/drive.file`

**Description**  
Read and write access to files and folders that were created by the application or explicitly opened with it.

**What it allows**
- Create files
- Update files created or opened by the application
- Upload generated content
- Create some new content with narrower permissions than full `drive`

**What it does not reliably allow**
- Managing arbitrary existing user files across the Drive
- Full workspace organization over pre-existing content not associated with the application

**Why it matters**  
This is the least-privilege write scope commonly used when the application only needs to manage files it creates.

**Tools that can use it in narrower deployments**
- `create_file`
- `upload_pdf`
- `create_google_doc`

**Limitations for this connector**  
Because the target feature set includes moving, renaming, and organizing arbitrary user files and folders, this scope is not sufficient by itself for the intended management capabilities.

---

### 4. `https://www.googleapis.com/auth/documents`

**Description**  
Full access to Google Docs document contents through the Google Docs API.

**What it allows**
- Insert text into Google Docs
- Update document structure and content
- Use `documents.batchUpdate` to edit created documents

**Why it matters**  
Creating a Google Doc file in Drive is not enough if the connector also needs to write text into that document using the Google Docs API.

**Tools that use it**
- `create_google_doc`

**Important note**  
If the implementation uses the broad `drive` scope and the Docs API accepts that authorization path, this dedicated scope may not be strictly necessary in every deployment. However, many implementations keep it documented because it directly maps to document content editing responsibilities.

---

## Scope to Tool Mapping

The table below documents the intended relationship between scopes and MCP tools.

| Tool | Purpose | Minimum Practical Scope | Recommended Scope for Current Connector | Notes |
|---|---|---|---|---|
| `list_files` | List files and folders with metadata and path context | `drive.readonly` | `drive` | `drive` is recommended because the connector is evolving toward full workspace management and richer metadata access. |
| `get_file_text` | Read, export, and download file contents | `drive.readonly` | `drive` | Needed for Google Docs export, Sheets export, Slides export, PDFs, and text files. |
| `create_file` | Create plain text or generic files | `drive.file` | `drive` | `drive.file` works for application-created files only; `drive` is better for broader lifecycle management. |
| `create_folder` | Create folders anywhere in Drive | `drive.file` or `drive` depending on access pattern | `drive` | Full Drive management is the intended target. |
| `move_file` | Move a file or folder by updating parents | `drive` | `drive` | Requires modifying existing Drive objects, not just application-created content. |
| `rename_file` | Rename an existing file or folder | `drive` | `drive` | Requires write access to existing items. |
| `upload_pdf` | Generate and upload a PDF | `drive.file` | `drive` | The current requirements favor broader workspace management. |
| `create_google_doc` | Create a Google Doc and populate content | `drive.file` plus `documents` | `drive`, and optionally `documents` | If using Docs API content insertion, documenting `documents` remains useful. |

---

## Recommended Scope Strategy

### Recommended for the current connector

Use the broad Drive scope:

https://www.googleapis.com/auth/drive

### Recommended Scope for Current Connector

This is the recommended scope for the current connector because the requested feature set includes:

- Reading arbitrary files  
- Creating folders  
- Creating text files  
- Moving files and folders  
- Renaming files and folders  
- Organizing existing workspace content  
- Working beyond files created only by this application  

## Alternative Least-Privilege Configuration

If the connector is intentionally restricted, the following split can be used:

- https://www.googleapis.com/auth/drive.readonly  
- https://www.googleapis.com/auth/drive.file  
- https://www.googleapis.com/auth/documents  

However, this model is less suitable when the agent must reorganize arbitrary existing Drive content.