# Google Meet MCP Server — Connector

This module provides the `MeetClient` data connector for the Google Meet REST API v2.
It is the foundational layer for the Google Meet MCP server, responsible for all direct
API interaction with Google Meet and Drive.

## Purpose

The connector exposes a clean, typed Python interface over the Google Meet API v2
discovery service. It does **not** handle authentication or scope validation — that
responsibility belongs to the MCP server middleware layer.

## `MeetClient` Methods

| Method | Description |
|--------|-------------|
| `list_conference_records` | List past and active meeting records. |
| `list_recordings` | List MP4 recordings associated with a meeting. |
| `list_transcripts` | List available transcripts for a meeting. |
| `list_transcript_entries` | Extract granular text and participant info from a transcript. |
| `list_participants` | List join/leave times, display names, and user identities. |

## Authentication Model

This connector uses **stateless OAuth tokens**. It does NOT rely on Application
Default Credentials (ADC). The caller provides an `access_token` string which is
wrapped into a `google.oauth2.credentials.Credentials` object via the
`build_meet_credentials()` helper.

Token validation and scope enforcement are handled externally by the MCP server
middleware.

### Required OAuth Scopes

The following scopes are required for the Meet API v2:

- `https://www.googleapis.com/auth/meetings.space.readonly`
- `https://www.googleapis.com/auth/meetings.space.created`

## Error Handling

The connector translates `googleapiclient.errors.HttpError` into domain-specific
exceptions:

| HTTP Status | Exception | Description |
|-------------|-----------|-------------|
| 401, 403 | `AuthenticationError` | Invalid or insufficient credentials |
| 429 | `MeetApiQuotaError` | API quota exceeded |
| Other | `HttpError` (re-raised) | Unexpected API error |

## Running Tests

```bash
uv run --group mcp_meet --group dev python -m pytest mcp_servers/google_meet/tests/ -v
```
