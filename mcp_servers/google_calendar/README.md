# Google Calendar & Meet MCP Server

This MCP server provides a dual-interface connector for the **Google Calendar API (v3)** and the **Google Meet API (v2)**. It is designed to bridge the gap between "Scheduled Events" and "Meeting Content," allowing agents to retrieve not only *when* a meeting happened but also *what* was discussed via recordings and transcripts.

## Why Both APIs?

Modern productivity workflows require context and content to be unified:
- **Google Calendar (The Context)**: Tells you the participants, the duration, and the official meeting code (`abc-defg-hij`).
- **Google Meet (The Content)**: Provides the historical Meet sessions, the actual join/leave times of attendees, and links to the generated artifacts (MP4 recordings, Google Docs transcripts).

By combining these, an agent can perform complex queries like: *"Find the transcript from yesterday's 10 AM standup and summarize the action items."*

---

## Architectural Highlights

- **Standardized Schema Contracts**: Built exclusively using Pydantic `BaseModel`. All exposed tools receive well-defined `Request` objects and return consistent `Response` objects.
- **Traceability (Parameter Echoing)**: Response schemas dynamically inherit from their corresponding Requests and a common `BaseResponse`. This means every tool returns the `execution_status` ("success" or "error"), the `execution_message`, and crucially, echoes back the original input parameters. The Agent never loses context when attempting rollbacks or compensations. 
- **Graceful Error Handling**: Instead of raising raw runtime exceptions on API HTTP errors, the Server catches exceptions and securely returns them wrapped within the `BaseResponse` standard format.
- **Unified Observability**: Leveraging `loguru`, the server implements tiered logging natively down to private components: `DEBUG` for mapping and fetching, `INFO` for unified routing boundaries, and `ERROR` for API exceptions.
 
---

## Components

### [Calendar Client](./app/calendar/README.md)
Handles high-level event retrieval, filtering by time range, and querying by text.
- **Key Task**: Resolving event titles into meeting codes.

### [Meet Client](./app/meet/README.md)
Handles deep-dive meeting metadata and artifact retrieval using the Meet v2 REST API.
- **Key Task**: Fetching recordings and transcripts for a specific session.

---

## Required OAuth Scopes

To use all features of this server, your OAuth token must include:

> [!IMPORTANT]
> **Calendar Scopes**
> - `https://www.googleapis.com/auth/calendar.events.readonly`
>
> **Meet v2 Scopes**
> - `https://www.googleapis.com/auth/meetings.space.readonly`

---

## Quick Start & Make Commands

The project manages continuous integration and local development through `uv` and the global repository `Makefile`.

### 1. Installation

Sync the exact dependencies for the calendar server securely using your `uv.lock`:
```bash
uv sync --group mcp_calendar --all-groups --locked
```

### 2. Running Locally

We have registered a port footprint across our system to avoid collisions. The Calendar MCP runs locally on port `8083`:
```bash
make run-calendar-mcp-locally
```

### 3. Running Tests & QA

We maintain a robust test suite covering RFC3339 validation, base response schema inheritance, parameter echoing edge cases, and API failure modes.

Run your tests using Make:
```bash
make run-calendar-tests
```

Or verify the entire pipeline (Pre-commit, Pytest, and Docker Build):
```bash
make verify-calendar-ci
```

---

## Technical Glossary

### Spaces vs. Sessions
- **Space**: The persistent "meeting room" with a fixed code (`abc-defg-hij`).
- **Session (Meet Session Record)**: A single timed instance of a meeting. A new session is created every time the meeting link is opened, even if the user does not fully join.
- **Active Session Filtering**: The `MeetClient` automatically **ignores empty sessions**. Only records where at least one participant actually joined are processed and returned.

## Technical Gotchas

- **RFC3339 Strictness**: Both APIs are extremely sensitive to date/time formatting. Always include the timezone offset (e.g., `Z` or `-05:00`).
- **Artifact Processing**: Meet recordings and transcripts are not available instantly. There is a processing lag of several minutes after a session ends.
