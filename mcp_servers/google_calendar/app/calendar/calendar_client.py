from loguru import logger
from typing import Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .config import CALENDAR_CONFIG
from .schemas import (
    CalendarEvent,
    Attendee,
    ConferenceData,
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

    def _parse_attendees(
        self, raw_attendees: list, organizer_dict: dict
    ) -> list[Attendee]:
        """Parses the raw attendee list and organizer into Attendee objects.

        Args:
            raw_attendees (list): The list of attendees from the API.
            organizer_dict (dict): The organizer information from the API.

        Return:
            list[Attendee]: A list of Attendee objects.
        """
        attendees = []
        for attendee in raw_attendees:
            attendees.append(
                Attendee(
                    email=attendee.get("email", ""),
                    display_name=attendee.get("displayName"),
                    response_status=attendee.get("responseStatus"),
                    organizer=attendee.get("organizer", False),
                    optional=attendee.get("optional", False),
                )
            )

        # Ensure organizer is in attendees list if not already there
        if organizer_dict and not any(
            attendee_obj.email == organizer_dict.get("email")
            for attendee_obj in attendees
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
        return attendees

    def _parse_conference_data(self, conf_data_dict: dict) -> list[ConferenceData]:
        """Parses conference data into ConferenceData objects.

        Args:
            conf_data_dict (dict): The conference data from the API.

        Return:
            list[ConferenceData]: A list of ConferenceData objects.
        """
        conference_info = []
        conf_id = conf_data_dict.get("conferenceId")
        if conf_id:
            for entry_point in conf_data_dict.get("entryPoints", []):
                uri = entry_point.get("uri")
                if uri:
                    conference_info.append(
                        ConferenceData(joining_url=uri, conference_id=conf_id)
                    )
        return conference_info

    def _parse_attachments(self, raw_attachments: list) -> list[EventAttachment]:
        """Parses raw attachments into EventAttachment objects.

        Args:
            raw_attachments (list): The list of attachments from the API.

        Return:
            list[EventAttachment]: A list of EventAttachment objects.
        """
        attachments = []
        for attachment in raw_attachments:
            attachments.append(
                EventAttachment(
                    file_id=attachment.get("fileId"),
                    file_url=attachment.get("fileUrl", ""),
                    title=attachment.get("title"),
                    mime_type=attachment.get("mimeType"),
                )
            )
        return attachments

    def _format_time_filters(
        self,
        date_min: Optional[str] = None,
        time_min: Optional[str] = None,
        date_max: Optional[str] = None,
        time_max: Optional[str] = None,
    ) -> dict[str, Optional[str]]:
        """Formats dates and times into RFC3339 strings for the API.

        Args:
            date_min (str | None): Start date (YYYY-MM-DD).
            time_min (str | None): Start time (HH:MM:SSZ).
            date_max (str | None): End date (YYYY-MM-DD).
            time_max (str | None): End time (HH:MM:SSZ).

        Returns:
            dict[str, str | None]: A dictionary with 'formatted_time_min' and 'formatted_time_max' keys.
        """
        # Identify base dates with pro-active synchronization
        base_date_min = date_min
        if not base_date_min and time_min and date_max:
            # Fallback to date_max for time_min if date_min is missing
            base_date_min = date_max

        base_date_max = date_max
        if not base_date_max and time_max and date_min:
            # Fallback to date_min for time_max if date_max is missing
            base_date_max = date_min

        # Process Lower Bound (Min)
        if base_date_min:
            formatted_min = (
                f"{base_date_min}T{time_min or CALENDAR_CONFIG.default_start_time}"
            )
        else:
            formatted_min = time_min

        # Process Upper Bound (Max)
        if base_date_max:
            formatted_max = (
                f"{base_date_max}T{time_max or CALENDAR_CONFIG.default_end_time}"
            )
        else:
            formatted_max = time_max

        return {
            "formatted_time_min": formatted_min,
            "formatted_time_max": formatted_max,
        }

    def _fetch_calendar_events(
        self,
        max_events: int,
        date_min: Optional[str] = None,
        time_min: Optional[str] = None,
        date_max: Optional[str] = None,
        time_max: Optional[str] = None,
        query: Optional[str] = None,
    ) -> list[dict]:
        """Queries Google Calendar API to fetch raw event data.

        Args:
            max_events (int): The maximum number of events to return.
            date_min (str | None): Optional lower bound date filter (YYYY-MM-DD).
            time_min (str | None): Optional lower bound time filter (HH:MM:SSZ).
            date_max (str | None): Optional upper bound date filter (YYYY-MM-DD).
            time_max (str | None): Optional upper bound time filter (HH:MM:SSZ).
            query (str | None): Optional free-text search terms. Searches across title, description, location and other event fields.

        Return:
            list[dict]: A list of raw event items from the API.
        """
        logger.debug("Fetching raw calendar events from API...")
        kwargs = {
            "calendarId": CALENDAR_CONFIG.calendar_id,
            "singleEvents": True,
            "maxResults": max_events,
            "orderBy": "startTime",
        }

        if query:
            kwargs["q"] = query

        # Format datetimes delegation
        formatted_times = self._format_time_filters(
            date_min=date_min,
            time_min=time_min,
            date_max=date_max,
            time_max=time_max,
        )

        if formatted_times["formatted_time_min"]:
            kwargs["timeMin"] = formatted_times["formatted_time_min"]
        if formatted_times["formatted_time_max"]:
            kwargs["timeMax"] = formatted_times["formatted_time_max"]

        try:
            logger.debug(f"Executing Calendar API request with kwargs: {kwargs}")
            events_result = self.calendar.events().list(**kwargs).execute()
        except Exception as exc:
            logger.exception(f"Failed to fetch events from Google Calendar API: {exc}")
            return []

        return events_result.get("items", [])

    def list_events(
        self,
        max_events: int,
        date_min: Optional[str] = None,
        time_min: Optional[str] = None,
        date_max: Optional[str] = None,
        time_max: Optional[str] = None,
        query: Optional[str] = None,
    ) -> list[CalendarEvent]:
        """Fetch and parse calendar events into structured models.

        Args:
            max_events (int): The maximum number of events to return.
            date_min (str | None): Optional lower bound date filter (YYYY-MM-DD).
            time_min (str | None): Optional lower bound time filter (HH:MM:SSZ).
            date_max (str | None): Optional upper bound date filter (YYYY-MM-DD).
            time_max (str | None): Optional upper bound time filter (HH:MM:SSZ).
            query (str | None): Optional free-text search terms. Searches across title, description, location and other event fields.

        Return:
            list[CalendarEvent]: A list of parsed CalendarEvent objects.
        """
        logger.info("Fetching calendar events...")
        logger.debug(f"Max events: {max_events}")
        logger.debug(f"Date min: {date_min}")
        logger.debug(f"Time min: {time_min}")
        logger.debug(f"Date max: {date_max}")
        logger.debug(f"Time max: {time_max}")
        logger.debug(f"Query: {query}")

        raw_items = self._fetch_calendar_events(
            max_events=max_events,
            date_min=date_min,
            time_min=time_min,
            date_max=date_max,
            time_max=time_max,
            query=query,
        )

        logger.info(f"Parsing {len(raw_items)} events into CalendarEvent models")
        events = []

        for event in raw_items:
            attendees = self._parse_attendees(
                raw_attendees=event.get("attendees", []),
                organizer_dict=event.get("organizer", {}),
            )
            conference_info = self._parse_conference_data(
                event.get("conferenceData", {})
            )
            attachments = self._parse_attachments(event.get("attachments", []))

            # Parse times
            start_event = event.get("start", {})
            end_event = event.get("end", {})
            start_dt = start_event.get("dateTime") or start_event.get(
                "date"
            )  # To include events that span multiple days
            end_dt = end_event.get("dateTime") or end_event.get(
                "date"
            )  # To include events that span multiple days

            events.append(
                CalendarEvent(
                    event_id=event.get("id"),
                    title=event.get("summary"),
                    description=event.get("description"),
                    event_status=event.get("status"),
                    location=event.get("location"),
                    start_time=start_dt,
                    end_time=end_dt,
                    attendees=attendees,
                    conference_info=conference_info,
                    attachments=attachments,
                )
            )

        return events
