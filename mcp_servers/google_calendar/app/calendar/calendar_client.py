from loguru import logger
from typing import Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .config import CALENDAR_CONFIG
from .schemas import (
    CalendarEvent,
    Attendee,
    ConferenceData,
    EventStatus,
    ResponseStatus,
    EventAttachment,
)


class CalendarClient:
    """Primary connector for Google Calendar API to fetch Events."""

    def __init__(self, creds: Credentials) -> None:
        """Initializes the CalendarClient with Google API credentials.

        Args:
            creds (Credentials): Valid Google OAuth2 credentials.

        Return:
            None
        """
        self.creds = creds
        self.calendar = build(
            CALENDAR_CONFIG.calendar_api_service_name,
            CALENDAR_CONFIG.calendar_api_version,
            credentials=creds,
            cache_discovery=False,
        )
        logger.info(
            f"Initialized CalendarClient with service: {CALENDAR_CONFIG.calendar_api_service_name} {CALENDAR_CONFIG.calendar_api_version}"
        )

    def _get_calendar_events(
        self,
        max_events: int,
        date_min: Optional[str] = None,
        time_min: Optional[str] = None,
        date_max: Optional[str] = None,
        time_max: Optional[str] = None,
        title: Optional[str] = None,
    ) -> list[CalendarEvent]:
        """Queries Google Calendar API to fetch events based on time limits and optional title.

        Args:
            max_events (int): The maximum number of events to return.
            date_min (str | None): Optional lower bound date filter (YYYY-MM-DD).
            time_min (str | None): Optional lower bound time filter (HH:MM:SSZ).
            date_max (str | None): Optional upper bound date filter (YYYY-MM-DD).
            time_max (str | None): Optional upper bound time filter (HH:MM:SSZ).
            title (str | None): Optional title text search.

        Return:
            list[CalendarEvent]: A list of CalendarEvent objects.
        """
        logger.debug("Getting calendar events...")
        logger.debug(f"Max events: {max_events}")
        logger.debug(f"Date min: {date_min}")
        logger.debug(f"Time min: {time_min}")
        logger.debug(f"Date max: {date_max}")
        logger.debug(f"Time max: {time_max}")
        logger.debug(f"Title: {title}")

        kwargs = {
            "calendarId": CALENDAR_CONFIG.calendar_id,
            "singleEvents": True,
            "maxResults": max_events,
            "orderBy": "startTime",
            "supportsAttachments": True,
        }

        if title:
            kwargs["q"] = title

        # Format datetimes according to rfc3339 constraints, merging dates and times
        logger.debug("Formatting dates and times to rfc3339 constraints")
        if date_min:
            kwargs["timeMin"] = (
                f"{date_min}T{time_min or CALENDAR_CONFIG.default_start_time}"
            )
        elif time_min:
            kwargs["timeMin"] = time_min

        if date_max:
            kwargs["timeMax"] = (
                f"{date_max}T{time_max or CALENDAR_CONFIG.default_end_time}"
            )
        elif time_max:
            kwargs["timeMax"] = time_max

        try:
            logger.debug(f"Executing Calendar API request with kwargs: {kwargs}")
            events_result = self.calendar.events().list(**kwargs).execute()
        except Exception as exc:
            logger.exception(f"Failed to fetch events from Google Calendar API: {exc}")
            return []

        raw_items = events_result.get("items", [])
        logger.info(
            f"Successfully fetched {len(raw_items)} raw events from Calendar API"
        )
        events = []

        for event in raw_items:
            # Parse attendees
            attendees = []
            for a in event.get("attendees", []):
                resp_status = a.get("responseStatus")
                try:  # try mapping string to Enum
                    resp_status_enum = (
                        ResponseStatus(resp_status)
                        if resp_status
                        else ResponseStatus.NEEDS_ACTION
                    )
                except ValueError:
                    logger.warning(
                        f"Invalid response status: {resp_status}. Setting to NEEDS_ACTION"
                    )
                    resp_status_enum = ResponseStatus.NEEDS_ACTION

                attendees.append(
                    Attendee(
                        email=a.get("email", ""),
                        display_name=a.get("displayName"),
                        response_status=resp_status_enum,
                        organizer=a.get("organizer", False),
                        optional=a.get("optional", False),
                    )
                )

            # Ensure organizer is in attendees list if not already there
            organizer_dict = event.get("organizer", {})
            if organizer_dict and not any(
                att.email == organizer_dict.get("email") for att in attendees
            ):
                attendees.append(
                    Attendee(
                        email=organizer_dict.get("email", ""),
                        display_name=organizer_dict.get("displayName"),
                        response_status=ResponseStatus.ACCEPTED,
                        organizer=True,
                        optional=False,
                    )
                )

            # Parse conference data
            conference_info = []
            conf_data_dict = event.get("conferenceData", {})
            conf_id = conf_data_dict.get("conferenceId")
            if conf_id:
                for entry in conf_data_dict.get("entryPoints", []):
                    # We might want to filter only by video entry points
                    uri = entry.get("uri")
                    if uri:
                        conference_info.append(
                            ConferenceData(joining_url=uri, conference_id=conf_id)
                        )

            # Parse attachments
            attachments = []
            for att in event.get("attachments", []):
                attachments.append(
                    EventAttachment(
                        file_id=att.get("fileId"),
                        file_url=att.get("fileUrl"),
                        title=att.get("title"),
                        mime_type=att.get("mimeType"),
                    )
                )

            # Parse times
            start_dt = event.get("start", {}).get("dateTime") or event.get(
                "start", {}
            ).get("date")
            end_dt = event.get("end", {}).get("dateTime") or event.get("end", {}).get(
                "date"
            )

            event_status_str = event.get("status")
            try:
                event_status = (
                    EventStatus(event_status_str) if event_status_str else None
                )
            except ValueError:
                event_status = None

            events.append(
                CalendarEvent(
                    id=event.get("id", ""),
                    title=event.get("summary"),
                    description=event.get("description"),
                    event_status=event_status,
                    start_time=start_dt,
                    end_time=end_dt,
                    attendees=attendees,
                    conference_info=conference_info,
                    attachments=attachments,
                )
            )

        logger.info(f"Returning {len(events)} parsed CalendarEvent objects")
        return events
