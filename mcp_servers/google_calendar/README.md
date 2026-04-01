# Google Calendar & Meet MCP Server

This MCP server provides a dual-interface connector for the **Google Calendar API (v3)** and the **Google Meet API (v2)**. It is designed to bridge the gap between "Scheduled Events" and "Meeting Content," allowing agents to retrieve not only *when* a meeting happened but also *what* was discussed via recordings and transcripts.

## Why Both APIs?

Modern productivity workflows require context and content to be unified:
- **Google Calendar (The Context)**: Tells you the participants, the duration, and the official meeting code (`abc-defg-hij`).
- **Google Meet (The Content)**: Provides the historical conference records, the actual join/leave times of attendees, and links to the generated artifacts (MP4 recordings, Google Docs transcripts).

By combining these, an agent can perform complex queries like: *"Find the transcript from yesterday's 10 AM standup and summarize the action items."*

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

## Quick Start

### 1. Installation
This project uses `uv` for dependency management.

```bash
uv sync --group mcp_calendar
```

### 2. Running Tests
We maintain a robust test suite covering RFC3339 validation and API error handling.

```bash
uv run pytest mcp_servers/google_calendar/tests/
```

---

## Technical Gotchas

- **RFC3339 Strictness**: Both APIs are extremely sensitive to date/time formatting. Always include the timezone offset (e.g., `Z` or `-05:00`).
- **Artifact Processing**: Meet recordings and transcripts are not available instantly. There is a processing lag of several minutes after a session ends.
