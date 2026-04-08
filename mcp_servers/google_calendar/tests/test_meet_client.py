from unittest.mock import MagicMock, patch
import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response as Httplib2Response

from mcp_servers.google_calendar.app.meet.meet_client import MeetClient
from mcp_servers.google_calendar.app.meet.schemas import ArtifactStatus, UserType

# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture
def mock_build():
    with patch("mcp_servers.google_calendar.app.meet.meet_client.build") as mock:
        yield mock


@pytest.fixture
def meet_client(mock_build):
    return MeetClient(MagicMock())


def _make_http_error(status_code: int) -> HttpError:
    resp = Httplib2Response({"status": status_code})
    return HttpError(resp=resp, content=b"error")


# -----------------------------------------------------------------------
# Initialization
# -----------------------------------------------------------------------


def test_meet_client_init(mock_build):
    creds = MagicMock()
    client = MeetClient(creds)
    assert client.creds is creds
    mock_build.assert_called_once()


# -----------------------------------------------------------------------
# list_meet_sessions
# -----------------------------------------------------------------------


def test_list_meet_sessions_success(meet_client, mock_build):
    mock_meet = mock_build.return_value

    # 1. Mock _resolve_space_name
    mock_meet.spaces.return_value.get.return_value.execute.return_value = {
        "name": "spaces/abc-123"
    }

    # 2. Mock _fetch_meet_sessions
    mock_meet.conferenceRecords.return_value.list.return_value.execute.return_value = {
        "conferenceRecords": [
            {
                "name": "conferenceRecords/session-1",
                "startTime": "2026-03-30T10:00:00Z",
                "endTime": "2026-03-30T11:00:00Z",
            }
        ]
    }

    # 3. Mock artifact fetches
    mock_meet.conferenceRecords.return_value.recordings.return_value.list.return_value.execute.return_value = {
        "recordings": []
    }
    mock_meet.conferenceRecords.return_value.transcripts.return_value.list.return_value.execute.return_value = {
        "transcripts": []
    }
    mock_meet.conferenceRecords.return_value.participants.return_value.list.return_value.execute.return_value = {
        "participants": [
            {"name": "p1", "signedinUser": {"user": "u1", "displayName": "User 1"}}
        ]
    }

    sessions = meet_client.list_meet_sessions(meeting_code="abc-123")

    assert len(sessions) == 1
    assert sessions[0].meeting_code == "abc-123"
    assert sessions[0].session_id == "conferenceRecords/session-1"
    assert sessions[0].total_participants == 1


def test_list_meet_sessions_no_space(meet_client, mock_build):
    mock_meet = mock_build.return_value
    # Mock spaces.get to fail
    mock_meet.spaces.return_value.get.return_value.execute.side_effect = (
        _make_http_error(404)
    )

    sessions = meet_client.list_meet_sessions(meeting_code="missing-id")
    assert sessions == []


# -----------------------------------------------------------------------
# get_meet_recording & get_meet_transcript
# -----------------------------------------------------------------------


def test_list_meet_participants_success(meet_client, mock_build):
    mock_meet = mock_build.return_value
    mock_meet.conferenceRecords.return_value.participants.return_value.list.return_value.execute.return_value = {
        "participants": [
            {
                "name": "p-1",
                "earliestStartTime": "2026-03-30T10:00:00Z",
                "latestEndTime": "2026-03-30T11:00:00Z",
                "signedinUser": {"displayName": "User 1", "user": "users/1"},
            }
        ]
    }

    participants = meet_client.list_meet_participants(
        meet_session_id="conferenceRecords/session-123"
    )
    assert len(participants) == 1
    assert participants[0].display_name == "User 1"


def test_get_meet_recording_success(meet_client, mock_build):
    mock_meet = mock_build.return_value
    mock_meet.conferenceRecords.return_value.recordings.return_value.get.return_value.execute.return_value = {
        "name": "rec-1",
        "state": "FILE_GENERATED",
        "startTime": "2026-03-30T10:00:00Z",
        "endTime": "2026-03-30T11:00:00Z",
        "driveDestination": {"file": "file-123"},
    }

    recording = meet_client.get_meet_recording("rec-1")
    assert recording.recording_id == "rec-1"
    assert recording.drive_file_id == "file-123"
    assert recording.state == ArtifactStatus.FILE_GENERATED


def test_get_meet_recording_not_found_raises(meet_client, mock_build):
    mock_meet = mock_build.return_value
    mock_meet.conferenceRecords.return_value.recordings.return_value.get.return_value.execute.side_effect = _make_http_error(
        404
    )

    with pytest.raises(HttpError):
        meet_client.get_meet_recording("deleted-rec")


# -----------------------------------------------------------------------
# Mapping Edge Cases
# -----------------------------------------------------------------------


def test_map_participant_unknown_structure(meet_client):
    # Raw data missing signedinUser, anonymousUser, and phoneUser
    raw_data = {
        "name": "p-1",
        "earliestStartTime": "2026-03-30T10:00:00Z",
        "latestEndTime": "2026-03-30T11:00:00Z",
    }
    attendee = meet_client._map_participant(raw_data)

    assert attendee.display_name == "Unknown Participant"
    assert attendee.user_id == "ANONYMOUS"
    assert attendee.user_type == UserType.ANONYMOUS


def test_map_participant_signed_in(meet_client):
    raw_data = {
        "signedinUser": {"user": "users/123", "displayName": "Alice"},
        "earliestStartTime": "2026-03-30T10:00:00Z",
        "latestEndTime": "2026-03-30T11:00:00Z",
    }
    attendee = meet_client._map_participant(raw_data)
    assert attendee.display_name == "Alice"
    assert attendee.user_id == "users/123"
    assert attendee.user_type == UserType.SIGNED_IN
