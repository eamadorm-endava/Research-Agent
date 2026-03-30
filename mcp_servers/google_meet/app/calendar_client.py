from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .config import CALENDAR_CONFIG

logger = logging.getLogger(__name__)


class CalendarClient:
    """Stateless connector for Google Calendar API.

    This client is used to find associated meeting codes and retrieve
    event titles and descriptions to enrich Meet records.
    """

    def __init__(self, creds: Credentials) -> None:
        self.creds = creds
        self.calendar = build(
            CALENDAR_CONFIG.calendar_api_service_name,
            CALENDAR_CONFIG.calendar_api_version,
            credentials=creds,
            cache_discovery=False,
        )
        logger.info(
            f"Initialized CalendarClient with Calendar ({CALENDAR_CONFIG.calendar_api_version})"
        )

    def find_meeting_ids(
        self,
        conference_name: Optional[str] = None,
        event_status: Optional[str] = None,
    ) -> set[str]:
        """Search Google Calendar for events matching various criteria.

        Args:
            conference_name (str | None): The search query (title contains).
            event_status (str | None): Filter by current user's attendee status.

        Returns:
            set[str]: A set of unique meeting codes/IDs.
        """
        logger.info("Initiating Google Calendar search")
        logger.debug(f"Parameters: {conference_name=}, {event_status=}")
        meeting_codes: set[str] = set()

        try:
            kwargs = {
                "calendarId": CALENDAR_CONFIG.calendar_id,
                "singleEvents": True,
                "maxResults": CALENDAR_CONFIG.max_calendar_search_results,
            }
            if conference_name:
                kwargs["q"] = conference_name

            events_result = self.calendar.events().list(**kwargs).execute()
            events = events_result.get("items", [])
            logger.debug(f"Found {len(events)} initial events in Calendar")

            for event in events:
                # Filter by status
                if event_status:
                    attendees = event.get("attendees", [])
                    self_attendee = next((a for a in attendees if a.get("self")), None)
                    actual_status = (
                        self_attendee.get("responseStatus") if self_attendee else None
                    )

                    if not actual_status and event.get("organizer", {}).get("self"):
                        actual_status = "accepted"

                    if actual_status != event_status.lower():
                        logger.debug(
                            f"Skipping event {event.get('id')}: status {actual_status} != {event_status}"
                        )
                        continue

                # Extract meeting codes from conferenceData
                conf_data = event.get("conferenceData", {})
                entry_points = conf_data.get("entryPoints", [])

                discovered_in_event = 0
                for entry in entry_points:
                    if entry.get("entryPointType") == CALENDAR_CONFIG.video_entry_point:
                        uri = entry.get("uri", "")
                        if CALENDAR_CONFIG.meet_url_prefix in uri:
                            code = uri.split("/")[-1]
                            meeting_codes.add(code)
                            discovered_in_event += 1

                conf_id = conf_data.get("conferenceId")
                if conf_id:
                    meeting_codes.add(conf_id)
                    discovered_in_event += 1

                if discovered_in_event:
                    logger.debug(f"Extracted codes from event {event.get('id')}")

        except Exception as exc:
            logger.warning(f"Calendar search failed: {str(exc)}", exc_info=True)

        logger.info(f"Final discovered meeting codes: {len(meeting_codes)}")
        logger.debug(f"Codes: {meeting_codes}")
        return meeting_codes

    def get_event_details_by_meeting_code(
        self,
        meeting_code: str,
        start_time_iso: str,
    ) -> dict[str, str | None] | None:
        """Fetch title and description for an event containing a meeting code.

        Args:
            meeting_code (str): The meeting URI or code.
            start_time_iso (str): The ISO format start time to bound the search.

        Returns:
            dict | None: Dictionary containing 'title' and 'description' if found.
        """
        logger.info(f"Looking up event details for meeting code: {meeting_code}")
        try:
            start_str = start_time_iso
            if start_str.endswith("Z"):
                start_str = start_str[:-1] + "+00:00"
            start_dt = datetime.fromisoformat(start_str)

            time_min = (start_dt - timedelta(hours=1)).isoformat()
            time_max = (start_dt + timedelta(hours=12)).isoformat()

            events_result = (
                self.calendar.events()
                .list(
                    calendarId=CALENDAR_CONFIG.calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            for ev in events:
                conf_data = ev.get("conferenceData", {})
                is_match = False

                if conf_data.get("conferenceId") == meeting_code:
                    is_match = True
                else:
                    for ep in conf_data.get("entryPoints", []):
                        if meeting_code in ep.get("uri", ""):
                            is_match = True
                            break

                if is_match:
                    logger.info(f"Successfully matched event for {meeting_code}")
                    return {
                        "title": ev.get("summary"),
                        "description": ev.get("description"),
                    }

            logger.debug(f"No matching Calendar details found for {meeting_code}")
            return None

        except Exception as exc:
            logger.warning(
                f"Calendar enrichment failed for {meeting_code}: {str(exc)}",
                exc_info=True,
            )
            return None
