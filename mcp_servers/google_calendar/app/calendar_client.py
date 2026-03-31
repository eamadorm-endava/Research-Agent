from __future__ import annotations

import logging
from typing import Any, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .config import CALENDAR_CONFIG
from .meet_client import MeetClient
from .drive_client import DriveClient
from .schemas import CalendarEventModel, AttendeeModel

logger = logging.getLogger(__name__)


class CalendarClient:
    """Primary connector for Google Calendar API.

    This client coordinates the fetching of Calendar Events and delegates
    fetching recording/transcript artifacts to MeetClient and DriveClient.
    """

    def __init__(self, creds: Credentials) -> None:
        self.creds = creds
        self.calendar = build(
            CALENDAR_CONFIG.calendar_api_service_name,
            CALENDAR_CONFIG.calendar_api_version,
            credentials=creds,
            cache_discovery=False,
        )
        self.meet_client = MeetClient(creds)
        self.drive_client = DriveClient(creds)
        logger.info(
            f"Initialized CalendarClient with Calendar ({CALENDAR_CONFIG.calendar_api_version})"
        )

    def list_events(
        self,
        start_date: Optional[str] = None,
        start_time: Optional[str] = None,
        end_date: Optional[str] = None,
        end_time: Optional[str] = None,
        event_name: Optional[str] = None,
        has_meeting_recording: bool = False,
        has_transcript_file: bool = False,
        event_status: Optional[str] = None,
        max_results: int = CALENDAR_CONFIG.default_page_size,
    ) -> list[CalendarEventModel]:
        """Fetch Calendar Events, optionally enriched with Meet recordings and transcripts.

        Args:
            start_date (str | None): Starting date in YYYY-MM-DD format.
            start_time (str | None): Starting time in HH:MM:SSZ format.
            end_date (str | None): Ending date in YYYY-MM-DD format.
            end_time (str | None): Ending time in HH:MM:SSZ format.
            event_name (str | None): Text to search in event title.
            has_meeting_recording (bool): Filter to only events with Meet recordings.
            has_transcript_file (bool): Filter to only events with Meet transcripts.
            event_status (str | None): Current caller's response status (e.g. 'accepted').
            max_results (int): Exact number of calendar items to return.

        Returns:
            list[CalendarEventModel]: Enriched calendar events.
        """
        logger.info("Listing calendar events with given criteria.")

        # Build timeMin and timeMax
        time_min = None
        if start_date:
            full_start = (
                f"{start_date}T{start_time or CALENDAR_CONFIG.default_start_time}"
            )
            time_min = full_start

        time_max = None
        if end_date:
            full_end = f"{end_date}T{end_time or CALENDAR_CONFIG.default_end_time}"
            time_max = full_end

        # If filtering by media presence, fetch an internal chunk to ensure we hit quota
        fetch_limit = (
            min(max_results * 5, CALENDAR_CONFIG.max_calendar_search_results)
            if (has_meeting_recording or has_transcript_file)
            else min(max_results, CALENDAR_CONFIG.max_calendar_search_results)
        )

        kwargs: dict[str, Any] = {
            "calendarId": CALENDAR_CONFIG.calendar_id,
            "singleEvents": True,
            "maxResults": fetch_limit,
            "orderBy": "startTime",
        }
        if time_min:
            kwargs["timeMin"] = time_min
        if time_max:
            kwargs["timeMax"] = time_max
        if event_name:
            kwargs["q"] = event_name

        try:
            events_result = self.calendar.events().list(**kwargs).execute()
        except Exception as exc:
            logger.error(f"Failed to query Calendar API: {exc}", exc_info=True)
            return []

        raw_events = events_result.get("items", [])
        final_events = []

        for event in raw_events:
            if len(final_events) >= max_results:
                break

            # Filter by status
            if event_status:
                attendees = event.get("attendees", [])
                self_attendee = next((a for a in attendees if a.get("self")), None)
                actual_status = (
                    self_attendee.get("responseStatus") if self_attendee else None
                )

                if not actual_status and event.get("organizer", {}).get("self"):
                    actual_status = "accepted"

                if not actual_status:
                    actual_status = "needsAction"

                if (
                    actual_status != event_status.lower()
                    and event_status.lower() != "any"
                ):
                    continue

            # Parse attendees
            parsed_attendees = []
            for a in event.get("attendees", []):
                parsed_attendees.append(
                    AttendeeModel(
                        email=a.get("email"),
                        displayName=a.get("displayName"),
                        responseStatus=a.get("responseStatus"),
                    )
                )

            # Find meeting code
            conf_data = event.get("conferenceData", {})
            entry_points = conf_data.get("entryPoints", [])

            meeting_code = conf_data.get("conferenceId")
            if not meeting_code:
                for entry in entry_points:
                    if entry.get("entryPointType") == CALENDAR_CONFIG.video_entry_point:
                        uri = entry.get("uri", "")
                        if CALENDAR_CONFIG.meet_url_prefix in uri:
                            meeting_code = uri.split("/")[-1]
                            break

            # Metadata properties
            event_has_recording = False
            event_has_transcript = False
            recordings_list = []
            transcripts_list = []

            if meeting_code:
                # Ask MeetClient for artifacts
                try:
                    conf_records = (
                        self.meet_client.get_conference_records_by_meeting_code(
                            meeting_code=meeting_code,
                            start_date=start_date,
                            end_date=end_date,
                        )
                    )

                    for record in conf_records:
                        recs = self.meet_client.list_recordings(record.name)
                        if recs:
                            event_has_recording = True
                            recordings_list.extend(recs)

                        transc = self.meet_client.list_transcripts(record.name)
                        if transc:
                            event_has_transcript = True
                            transcripts_list.extend(transc)
                except Exception as exc:
                    logger.warning(
                        f"Failed to fetch Meet artifacts for code {meeting_code}: {exc}"
                    )

            if has_meeting_recording and not event_has_recording:
                continue

            if has_transcript_file and not event_has_transcript:
                continue

            # In some recurring events without overriding times, events may lack start/end if they are day events
            start_dt = event.get("start", {}).get("dateTime") or event.get(
                "start", {}
            ).get("date")
            end_dt = event.get("end", {}).get("dateTime") or event.get("end", {}).get(
                "date"
            )

            event_model = CalendarEventModel(
                event_id=event.get("id"),
                title=event.get("summary"),
                description=event.get("description"),
                start_time=start_dt,
                end_time=end_dt,
                status=event.get("status"),
                meeting_code=meeting_code,
                has_recording=event_has_recording,
                has_transcript=event_has_transcript,
                attendees=parsed_attendees,
                recordings=recordings_list if recordings_list else None,
                transcripts=transcripts_list if transcripts_list else None,
            )
            final_events.append(event_model)

        logger.info(f"Returning {len(final_events)} fully parsed calendar events.")
        return final_events
