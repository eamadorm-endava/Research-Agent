# Meet Client Submodule

The `MeetClient` is an advanced connector for the **Google Meet REST API v2**. It provides tiered access to historical meeting data, recording artifacts, and granular participant logs.

## Purpose

- **Primary**: Resolve a 10-letter meeting code (e.g., `abc-defg-hij`) into a historical Meet session.
- **Secondary**: Retrieve metadata for generated assets such as **Recordings** (MP4) and **Transcripts** (Google Docs).
- **Tertiary**: Fetch detailed atomic logs of participant join and leave times.

---

## Technical Implementation Details

### 1. The Meeting Hierarchy

The Google Meet API v2 uses a tiered structure for historical data:

1.  **Space (The Room)**: The persistent "location" with a 10-letter code (e.g., `abc-defg-hij`).
2.  **Meet Session (The Occurrence)**: A specific, timed instance of a meeting within a Space. 
    *   **Trigger**: A new Session is created **every time** a user opens the meeting link, even if they do not successfully join or only stay for a few seconds.
3.  **Artifacts & Participants**: Recordings, transcripts, and attendee logs linked to a specific Meet Session.

> To reduce noise, the `MeetClient` automatically **filters out empty sessions**. Only sessions with at least one confirmed participant (`total_participants > 0`) are returned by the `list_meet_sessions` method.

### 2. Processing Lag

Post-meeting artifacts are produced by background Google processes entirely separate from the REST API.
- **Recordings**: May take several minutes to generate.
- **Transcripts**: May take even longer depending on the duration of the session.
- **States**: `MeetClient` uses the `ArtifactStatus` enum to track whether a file has been generated or is still "STARTED."

### 3. User Types

The v2 API categorizes participants into three distinct structures:
- `signedinUser`: Authenticated Google Account with a Display Name.
- `anonymousUser`: Guests who joined without signing in.
- `phoneUser`: Dial-in participants.

---

## Configuration (MeetConfig)

Adjust behavior via `MEET_CONFIG`:
- `participant_label_...`: Customize default names for signed-in, anonymous, or phone users if the API returns an empty field.
- `anonymous_user_id`: Fallback ID for guest participants.
- `meet_api_version`: Fixed at `v2`.

---

## Error Handling

| Scenario | Response |
| :--- | :--- |
| **Invalid/Deleted Meeting Code** | `_resolve_space_name` returns `""` and the search fails gracefully. |
| **No Conference Records Found** | Returns an empty list `[]`. |
| **403 Forbidden on Artifacts** | `get_meet_recording` and `get_meet_transcript` re-raise `HttpError` to let the caller handle it. |
| **Malformed Participant Data** | Defaults to "Unknown Participant" and "ANONYMOUS" user IDs. |
