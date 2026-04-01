# Meet Client Submodule

The `MeetClient` is an advanced connector for the **Google Meet REST API v2**. It provides tiered access to historical meeting data, recording artifacts, and granular participant logs.

## Purpose

- **Primary**: Resolve a 10-letter meeting code (e.g., `abc-defg-hij`) into a historical conference record.
- **Secondary**: Retrieve metadata for generated assets such as **Recordings** (MP4) and **Transcripts** (Google Docs).
- **Tertiary**: Fetch detailed atomic logs of participant join and leave times.

---

## Technical Implementation Details

### 1. The Meeting Hierarchy

The Meet v2 API is hierarchical. A user's "Meeting code" is actually an **Alias**.
1. **Space**: The persistent "Room" (`spaces/abcdefg`).
2. **Conference Record**: A specific instance or "Session" of a meeting within a space (`conferenceRecords/xyz-123`).
3. **Artifacts/Participants**: The findings *inside* a specific session.

> [!NOTE]
> **Resolution Flow**
> `MeetClient` resolved the code to a Space -> Lists all Conference Records for that Space -> Enrichment of each session with Participant counts and Artifact IDs.

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
| **403 Forbidden on Artifacts** | `get_recording_info` and `get_transcript_info` re-raise `HttpError` to let the caller handle it. |
| **Malformed Participant Data** | Defaults to "Unknown Participant" and "ANONYMOUS" user IDs. |
