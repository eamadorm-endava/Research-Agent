from typing import Optional
from google.oauth2.credentials import Credentials

from .calendar import CalendarClient
from .calendar.schemas import CalendarEvent
from .meet import MeetClient
from .meet.schemas import MeetSession, MeetParticipant, MeetRecording, MeetTranscript


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
            date_min (Optional[str]): Lower bound date filter (YYYY-MM-DD).
            time_min (Optional[str]): Lower bound time filter (HH:MM:SSZ).
            date_max (Optional[str]): Upper bound date filter (YYYY-MM-DD).
            time_max (Optional[str]): Upper bound time filter (HH:MM:SSZ).
            query (Optional[str]): Optional search terms.

        Returns:
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

    def list_meet_sessions(self, meeting_code: str) -> list[MeetSession]:
        """Lists and summarizes all Meet sessions for a specific meeting code.

        Args:
            meeting_code (str): The 10-letter Google Meet code (e.g., 'abc-defg-hij').

        Returns:
            list[MeetSession]: A list of objects summarizing each meeting session.
        """
        return self._meet.list_meet_sessions(meeting_code=meeting_code)

    def list_meet_participants(self, meet_session_id: str) -> list[MeetParticipant]:
        """Retrieves detailed participant data for a specific Meet session.

        Args:
            meet_session_id (str): Unique Meet session ID (e.g., 'conferenceRecords/abc-123-xyz').

        Returns:
            list[MeetParticipant]: A list of participants with join/leave metadata.
        """
        return self._meet.list_meet_participants(meet_session_id=meet_session_id)

    def get_meet_recording(self, recording_id: str) -> MeetRecording:
        """Retrieves detailed metadata for a specific Google Meet recording.

        Args:
            recording_id (str): The unique recording ID (e.g., 'conferenceRecords/abc/recordings/xyz').

        Returns:
            MeetRecording: A model containing the recording metadata.
        """
        return self._meet.get_meet_recording(recording_id=recording_id)

    def get_meet_transcript(self, transcript_id: str) -> MeetTranscript:
        """Retrieves detailed metadata for a specific Google Meet transcript.

        Args:
            transcript_id (str): The canonical resource ID of the transcript.

        Returns:
            MeetTranscript: A model containing transcript metadata.
        """
        return self._meet.get_meet_transcript(transcript_id=transcript_id)
