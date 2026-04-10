from loguru import logger
from typing import Optional, Union
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .config import CALENDAR_CONFIG
from .schemas import (
    CalendarEvent,
    Attendee,
    MeetSessionData,
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
        self, raw_attendees: list[dict], organizer_dict: dict[str, Union[str, bool]]
    ) -> list[Attendee]:
        """Parses the raw attendee list and organizer into Attendee objects.

        Args:
            raw_attendees (list): The list of attendees from the API.
            organizer_dict (dict): The organizer information from the API.

        Return:
            list[Attendee]: A list of Attendee objects.
        """
        logger.debug("Parsing attendees...")
        attendees = []
        for attendee in raw_attendees:
            attendees.append(
                Attendee(
                    email=attendee.get("email", ""),
                    user_id=attendee.get("id"),
                    display_name=attendee.get("displayName"),
                    response_status=attendee.get(
                        "responseStatus", ResponseStatus.NEEDS_ACTION
                    ),
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
                    user_id=organizer_dict.get("id"),
                    display_name=organizer_dict.get("displayName"),
                    response_status=ResponseStatus.ACCEPTED,
                    organizer=True,
                    optional=False,
                )
            )
        return attendees

    def _parse_meet_session_data(
        self, meet_data_dict: dict[str, Union[str, list, dict]]
    ) -> Optional[MeetSessionData]:
        """Parses Meet session data into a structured MeetSessionData object.

        Args:
            meet_data_dict (dict): The Meet session data from the Google Calendar API.

        Return:
            Optional[MeetSessionData]: A MeetSessionData object or None if no Meet link is found.
        """
        logger.debug("Parsing meet session data...")
        meeting_code = meet_data_dict.get("conferenceId")
        if not meeting_code:
            return None

        # Prioritize the video joining URL (Meet link)
        for entry_point in meet_data_dict.get("entryPoints", []):
            if entry_point.get("entryPointType") == "video":
                uri = entry_point.get("uri")
                if uri:
                    return MeetSessionData(joining_url=uri, meeting_code=meeting_code)

        for entry_point in meet_data_dict.get("entryPoints", []):
            uri = entry_point.get("uri")
            if uri:
                return MeetSessionData(joining_url=uri, meeting_code=meeting_code)

        return None

    def _parse_attachments(self, raw_attachments: list[dict]) -> list[EventAttachment]:
        """Parses raw attachments into EventAttachment objects.

        Args:
            raw_attachments (list): The list of attachments from the API.

        Return:
            list[EventAttachment]: A list of EventAttachment objects.
        """
        logger.debug("Parsing attachments...")
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

        Logic:
            The Google Calendar API (events.list) filters events that overlap with the range (timeMin, timeMax):
            - timeMin: Lower bound (exclusive) for an event's end time. Events ending before this are excluded.
            - timeMax: Upper bound (exclusive) for an event's start time. Events starting after this are excluded.
            This method ensures that both filters are valid RFC3339 strings by synchronizing missing date components
            from the available min/max parameters to avoid 400 Bad Request errors.

        Args:
            date_min (str | None): Start date (YYYY-MM-DD).
            time_min (str | None): Start time (HH:MM:SSZ).
            date_max (str | None): End date (YYYY-MM-DD).
            time_max (str | None): End time (HH:MM:SSZ).

        Returns:
            dict[str, str | None]: A dictionary with 'formatted_time_min' and 'formatted_time_max' keys.
        """
        formatted_min = None
        formatted_max = None

        # 1. Global Search: If all date/time parameters are None
        if not any([date_min, time_min, date_max, time_max]):
            logger.debug("No time filters provided. Performing a global search.")
            return {
                "formatted_time_min": formatted_min,
                "formatted_time_max": formatted_max,
            }

        # 2. Time without Date: Raise error if times are provided but dates are missing
        if (time_min or time_max) and (not date_min or not date_max):
            error_msg = (
                "Dates (date_min and date_max) are required when using time filters."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 3. Mandatory Date Pair: Raise error if only one date filter is provided
        if (date_min and not date_max) or (date_max and not date_min):
            error_msg = "Both date_min and date_max are required for a valid date-time search range."
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 4. Final Construction: If we reached here, we have both dates (if any temporal param was used)
        formatted_min = f"{date_min}T{time_min or '00:00:00Z'}"
        formatted_max = f"{date_max}T{time_max or '23:59:59Z'}"

        logger.debug(
            f"Final filters constructed: timeMin='{formatted_min}', timeMax='{formatted_max}'"
        )

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
            time_min (str | None): Optional lower bound time filter (HH:MM:SSZ). If setting a time zone, add the offset (e.g., "12:30:00-06:00").
            date_max (str | None): Optional upper bound date filter (YYYY-MM-DD).
            time_max (str | None): Optional upper bound time filter (HH:MM:SSZ). If setting a time zone, add the offset (e.g., "17:00:00-06:00").
            query (str | None): Optional free-text search terms. Searches across title, description, location and other event fields.

        Return:
            list[dict]: A list of raw event items from the API.
        """
        logger.debug("Fetching raw calendar events from API...")
        kwargs = {
            "calendarId": CALENDAR_CONFIG.calendar_id,
            "singleEvents": True,
            "maxResults": max_events,
            "orderBy": CALENDAR_CONFIG.order_by,
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
            logger.debug(f"Executing Calendar API request with parameters: {kwargs}")
            events_result = self.calendar.events().list(**kwargs).execute()
        except Exception as exc:
            error_msg = str(exc)
            if "400" in error_msg:
                logger.error(
                    "Google Calendar API returned a 400 Bad Request. "
                    "This is typically caused by invalid RFC3339 date/time formats. "
                    f"Check filters: timeMin={kwargs.get('timeMin')}, timeMax={kwargs.get('timeMax')}"
                )
            logger.exception(f"Detailed API Execution Error: {exc}")
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
            time_min (str | None): Optional lower bound time filter (HH:MM:SSZ). If setting a time zone, add the offset (e.g., "12:30:00-06:00").
            date_max (str | None): Optional upper bound date filter (YYYY-MM-DD).
            time_max (str | None): Optional upper bound time filter (HH:MM:SSZ). If setting a time zone, add the offset (e.g., "17:00:00-06:00").
            query (str | None): Optional natural language query. Searches across title, description, location and other event fields.

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
            meet_session = self._parse_meet_session_data(
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
                    meet_session=meet_session,
                    attachments=attachments,
                )
            )

        return events
