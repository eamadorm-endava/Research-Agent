# GCS MCP OAuth Validation and User-Scoped Authorization

This guide documents the delegated OAuth authentication model for the GCS MCP server and how to validate it with two different user profiles.

## ADR and Architecture Alignment

- Follow the project authentication ADR: delegated end-user OAuth token propagation from agent to MCP server.
- The MCP server remains stateless for auth storage.
- Token validation is performed at the MCP layer, and downstream Google Cloud Storage clients are created dynamically per request.

## Request Identity Context

Request schemas support an optional `user_identity_context` payload field for non-secret identity metadata (for example principal hint, authorization resource ID, session ID).

Important:
- Do not include raw bearer tokens in request payloads.
- Bearer tokens must travel through MCP `Authorization` headers.

## Runtime Authentication Flow

1. Agent sends MCP request with:
- `Authorization: Bearer <delegated-user-access-token>`
- Optional `X-Serverless-Authorization: Bearer <id-token>` for Cloud Run ingress

2. MCP server validates token against Google tokeninfo endpoint.

3. MCP server extracts current token from auth context and builds delegated credentials.

4. GCS client is instantiated for the request path and executes operations under user IAM.

5. Errors are normalized:
- Permission errors -> `Permission Denied`
- Not found errors -> `Object not found`

## Security Controls

- No long-lived JSON keys required.
- No plain-text token logging in application handlers.
- Error messages are sanitized to redact common token fragments.

### Landing Zone Data Ingestion Constraints
When the MCP Server reads files to ingest them into the Landing Zone:
1. **Payload Proof**: The server forces an OAuth-based 1-byte read (`f.read(1)`) to mathematically prove the user has `storage.objects.get` payload access before proceeding with ingestion. This prevents IDOR where a user might have metadata-only access but cannot read the actual file.
2. **Namespace Isolation**: Upon ingestion, the MCP Server uses its Service Account (which holds `roles/storage.admin`) to inject an IAM condition (`resource.name.startsWith(...)`) granting the user exclusive read access to their isolated namespace inside the Landing Zone bucket.
3. **Data Lifecycle**: The Landing Zone physically enforces a 7-day retention policy via Terraform-managed Object Lifecycle Management (OLM) rules, guaranteeing ephemeral storage cleanup.

## Automated Test Coverage

Current tests cover:
- Authorized user behavior for listing objects.
- Unauthorized user behavior for reading objects with normalized `Permission Denied`.
- Not-found behavior for reads with normalized `Object not found`.

Run tests:

```bash
uv run --group mcp_gcs pytest mcp_servers/gcs/tests/
```

## Two-Profile AI Agent E2E Validation

Use two real users with distinct GCS IAM roles:

- User A: has bucket/object read permission (`roles/storage.objectViewer` or stronger).
- User B: does not have permission on the same bucket/object.

### Procedure

1. Start GCS MCP server locally:

```bash
uv run --group mcp_gcs python -m mcp_servers.gcs.app.main --host localhost --port 8080
```

2. Connect the AI Agent to local GCS MCP endpoint (`/mcp`) and test with User A.
- Run `list_objects` and `read_object` on allowed bucket/object.
- Confirm success responses.

3. Repeat with User B.
- Run same calls.
- Confirm error responses with `Permission Denied` or `Object not found`.

4. Verify logs do not contain raw bearer tokens.

### Evidence Template

Capture and attach:
- User A result payloads (success)
- User B result payloads (denied)
- Brief IAM role mapping for both users
- Timestamped local run notes
