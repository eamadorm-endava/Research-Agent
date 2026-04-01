from typing import Optional
from google.oauth2.credentials import Credentials

from .calendar import CalendarClient
from .calendar.schemas import CalendarEvent
from .meet import MeetClient
from .meet.schemas import ConferenceSession, ConferenceAttendee, Recording, Transcript


class EventsClient:
    """The unified wrapper for both Google Calendar and Google Meet APIs.

    This client provides a single entry point for all operations, delegating
    requests to specialized sub-clients for Calendar (v3) and Meet (v2).
    """

    def __init__(self, creds: Credentials) -> None:
        """Initializes the EventsClient with Google API credentials.

        This sets up both the internal Calendar and Meet clients, sharing
         the same authorized session credentials.

        Args:
            creds (Credentials): Valid Google OAuth2 credentials.
        """
        self._calendar = CalendarClient(creds)
        self._meet = MeetClient(creds)

    # --- Calendar Client Delegation ---

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
            query (str | None): Optional search terms.

        Return:
            list[CalendarEvent]: A list of parsed CalendarEvent objects.
        """
        return self._calendar.list_events(
            max_events=max_events,
            date_min=date_min,
            time_min=time_min,
            date_max=date_max,
            time_max=time_max,
            query=query,
        )

    # --- Meet Client Delegation ---

    def list_conference_sessions(self, conference_id: str) -> list[ConferenceSession]:
        """Lists and summarizes all conference sessions for a specific meeting code.

        Args:
            conference_id (str): The 10-letter Google Meet code (e.g., 'abc-defg-hij').

        Returns:
            list[ConferenceSession]: A list of objects summarizing each session found.
        """
        return self._meet.list_conference_sessions(conference_id=conference_id)

    def get_participants_info(
        self, conference_session_id: str
    ) -> list[ConferenceAttendee]:
        """Retrieves detailed atomic participant data for a specific session ID.

        Args:
            conference_session_id (str): Canonical resource ID (e.g., 'conferenceRecords/abc-123').

        Returns:
            list[ConferenceAttendee]: A list of attendees with their join/leave metadata.
        """
        return self._meet.get_participants_info(
            conference_session_id=conference_session_id
        )

    def get_recording_info(self, recording_id: str) -> Recording:
        """Retrieves detailed atomic metadata for a specific Google Meet recording.

        Args:
            recording_id (str): The resource ID (e.g., 'conferenceRecords/abc/recordings/xyz').

        Returns:
            Recording: A model containing the recording metadata.
        """
        return self._meet.get_recording_info(recording_id=recording_id)

    def get_transcript_info(self, transcript_id: str) -> Transcript:
        """Retrieves detailed atomic metadata for a specific Google Meet transcript.

        Args:
            transcript_id (str): The canonical resource ID of the transcript.

        Returns:
            Transcript: A model containing transcript status and the Google Docs link.
        """
        return self._meet.get_transcript_info(transcript_id=transcript_id)
