# Calendar Client Submodule

The `CalendarClient` is responsible for all communication with the **Google Calendar API v3**. It focuses on retrieving scheduled event data, resolving meeting codes, and managing participant lists.

## Purpose

- **Primary**: Query the user's schedule to find past, current, or future events.
- **Secondary**: Extract `MeetSessionData` (meeting codes) from calendar events to feed into the `MeetClient`.
- **Tertiary**: Map diverse attendee types (including organizers) into a unified model.

---

## Technical Implementation Details

### 1. Chronological Sorting

> [!WARNING]
> **API Constraint**
> The Google Calendar API v3 **requires** `singleEvents=True` if you wish to use `orderBy="startTime"`.
> Our implementation automatically ensures this parameter is set correctly when sorting is enabled to prevent `400 Bad Request` errors.

### 2. RFC3339 Strictness

The Calendar API is extremely sensitive to date/time formatting in `timeMin` and `timeMax` parameters.
- **Good**: `2024-01-01T10:00:00Z` or `2024-01-01T10:00:00-05:00`
- **Bad**: `2024-01-01 10:00:00` (Space vs. `T`, no offset)

The `_format_time_filters` method in `CalendarClient` ensures these strings are constructed correctly to avoid common API failures.

---

## Configuration (CalendarConfig)

The client behavior can be adjusted via the `CALENDAR_CONFIG` object:
- `calendar_id`: Defaults to `primary`, but can target specific email-based or shared calendar IDs.
- `order_by`: Set to `startTime` by default for chronological retrieval.
- `calendar_api_version`: Fixed at `v3`.

---

## Error Handling

| Scenario | Response |
| :--- | :--- |
| **Malformed Date String** | Raises `ValueError` (caught locally, logged). |
| **Start Time > End Time** | Caught by validation logic, raises `ValueError`. |
| **403 Forbidden** | Logs the permission issue and returns an empty list `[]`. |
| **404 Not Found** | Logs the missing resource and returns an empty list `[]`. |
