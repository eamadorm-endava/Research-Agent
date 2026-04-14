# BigQuery MCP OAuth Validation and User-Scoped Access

This document describes how the BigQuery MCP server validates delegated OAuth tokens and enforces user-scoped authorization boundaries.

## Objective

Ensure that BigQuery operations run with the invoking end-user identity so the agent can only access datasets and tables that user is authorized to access.

## Required Configuration

1. Gemini Enterprise Authorization Resource
- Register an authorization resource with OAuth client credentials and BigQuery scopes.
- Attach this authorization to the ADK agent registration.

2. Agent-to-Server Transport
- MCP request must include:
  - `Authorization: Bearer <delegated-user-access-token>` for MCP OAuth validation.
  - `X-Serverless-Authorization: Bearer <cloud-run-id-token>` when Cloud Run IAM ingress is enabled.

3. BigQuery Scope
- Delegated token must include BigQuery scope (for example `https://www.googleapis.com/auth/bigquery`).

## Main Logic Implemented (BigQuery MCP)

1. OAuth token verification at MCP boundary
- `GoogleBigQueryTokenVerifier` validates incoming access tokens against Google tokeninfo endpoint.
- Invalid tokens are rejected before tool execution.

2. Dynamic per-request user credentials
- Each tool call resolves the current token from MCP auth context (`get_access_token`).
- The server builds `google.oauth2.credentials.Credentials` from that token.
- A BigQuery client is created with those credentials for that request path.

3. Permission-safe responses
- Permission-related backend errors are normalized to include `Permission Denied`.
- Tool responses return:
  - `execution_status: "error"`
  - `execution_message: "Permission Denied: ..."`

4. Sensitive-data handling
- Tool handlers do not log bearer tokens.
- Error sanitization redacts common token fragments before returning messages.

## Behavioral Expectations

- Authorized user:
  - Can list datasets/tables and execute queries for resources they are allowed to access.
- Unauthorized user:
  - Receives `execution_status: "error"` and `execution_message` containing `Permission Denied`.
  - No table/query data is returned.

## Automated Test Coverage

The BigQuery MCP test suite includes simulations for:
- Authorized user success in query execution.
- Unauthorized user blocked with normalized `Permission Denied` response.

Run tests:

```bash
uv run --group mcp_bq pytest mcp_servers/big_query/tests/
```

## Local End-to-End Validation with Two Profiles

Use two user profiles with different BigQuery IAM permissions:

1. Start BigQuery MCP server locally:

```bash
uv run --group mcp_bq python -m mcp_servers.big_query.app.main --host localhost --port 8080
```

2. Connect local AI agent to BigQuery MCP (`/mcp`) using profile A token (authorized).
- Validate a successful query/list_tables call.

3. Repeat with profile B token (unauthorized).
- Validate that calls return `execution_status: "error"` and `Permission Denied`.

4. Confirm no bearer token values appear in server logs.

Note: The exact token acquisition flow depends on your Gemini Enterprise and local ADK setup.