import pytest
from unittest.mock import MagicMock, patch
from google.oauth2.credentials import Credentials
from mcp_servers.google_calendar.app.connector import EventsClient


@pytest.fixture
def mock_creds():
    return MagicMock(spec=Credentials)


@pytest.fixture
def events_client(mock_creds):
    # Mock the discovery service to avoid network calls during initialization
    with (
        patch("mcp_servers.google_calendar.app.calendar.calendar_client.build"),
        patch("mcp_servers.google_calendar.app.meet.meet_client.build"),
    ):
        return EventsClient(mock_creds)


def test_events_client_initialization(mock_creds):
    """Verify that both sub-clients are initialized with the same credentials."""
    with (
        patch(
            "mcp_servers.google_calendar.app.calendar.calendar_client.build"
        ) as mock_cal_build,
        patch(
            "mcp_servers.google_calendar.app.meet.meet_client.build"
        ) as mock_meet_build,
    ):
        client = EventsClient(mock_creds)

        assert client._calendar is not None
        assert client._meet is not None

        # Verify the build calls used the right credentials
        mock_cal_build.assert_called_once()
        mock_meet_build.assert_called_once()

        assert "credentials" in mock_cal_build.call_args[1]
        assert mock_cal_build.call_args[1]["credentials"] == mock_creds


def test_list_events_delegation(events_client):
    """Verify list_events correctly delegates to the CalendarClient."""
    events_client._calendar.list_events = MagicMock(return_value=[])

    events_client.list_events(max_events=5, query="test")

    events_client._calendar.list_events.assert_called_once_with(
        max_events=5,
        date_min=None,
        time_min=None,
        date_max=None,
        time_max=None,
        query="test",
    )


def test_list_meet_sessions_delegation(events_client):
    """Verify list_meet_sessions correctly delegates to the MeetClient."""
    events_client._meet.list_meet_sessions = MagicMock(return_value=[])

    events_client.list_meet_sessions(meeting_code="abc-defg-hij")

    events_client._meet.list_meet_sessions.assert_called_once_with(
        meeting_code="abc-defg-hij"
    )


def test_list_meet_participants_delegation(events_client):
    """Verify list_meet_participants correctly delegates to the MeetClient."""
    events_client._meet.list_meet_participants = MagicMock(return_value=[])

    events_client.list_meet_participants(
        meet_session_id="conferenceRecords/session-123"
    )

    events_client._meet.list_meet_participants.assert_called_once_with(
        meet_session_id="conferenceRecords/session-123"
    )


def test_get_meet_recording_delegation(events_client):
    """Verify get_meet_recording correctly delegates to the MeetClient."""
    events_client._meet.get_meet_recording = MagicMock()

    events_client.get_meet_recording(
        recording_id="conferenceRecords/abc/recordings/xyz-123"
    )

    events_client._meet.get_meet_recording.assert_called_once_with(
        recording_id="conferenceRecords/abc/recordings/xyz-123"
    )


def test_get_meet_transcript_delegation(events_client):
    """Verify get_meet_transcript correctly delegates to the MeetClient."""
    events_client._meet.get_meet_transcript = MagicMock()

    events_client.get_meet_transcript(
        transcript_id="conferenceRecords/abc/transcripts/xyz-123"
    )

    events_client._meet.get_meet_transcript.assert_called_once_with(
        transcript_id="conferenceRecords/abc/transcripts/xyz-123"
    )
