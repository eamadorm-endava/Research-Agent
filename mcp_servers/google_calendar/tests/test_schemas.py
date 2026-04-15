import pytest
from pydantic import ValidationError

from mcp_servers.google_calendar.app.schemas import (
    BaseResponse,
    ListCalendarEventsRequest,
    ListCalendarEventsResponse,
    ListMeetSessionsRequest,
    ListMeetSessionsResponse,
    ListMeetParticipantsRequest,
    ListMeetParticipantsResponse,
    GetMeetRecordingRequest,
    GetMeetRecordingResponse,
    GetMeetTranscriptRequest,
    GetMeetTranscriptResponse,
)

# -----------------------------------------------------------------------
# Inheritance Tests
# -----------------------------------------------------------------------


def test_responses_inherit_from_base_response():
    """Ensure all response models inherit from BaseResponse."""
    assert issubclass(ListCalendarEventsResponse, BaseResponse)
    assert issubclass(ListMeetSessionsResponse, BaseResponse)
    assert issubclass(ListMeetParticipantsResponse, BaseResponse)
    assert issubclass(GetMeetRecordingResponse, BaseResponse)
    assert issubclass(GetMeetTranscriptResponse, BaseResponse)


def test_responses_inherit_from_request_eco_params():
    """Ensure that the required specific response models inherit from their respective requests for parameter echoing."""
    assert issubclass(ListMeetSessionsResponse, ListMeetSessionsRequest)
    assert issubclass(ListMeetParticipantsResponse, ListMeetParticipantsRequest)
    assert issubclass(GetMeetRecordingResponse, GetMeetRecordingRequest)
    assert issubclass(GetMeetTranscriptResponse, GetMeetTranscriptRequest)


# -----------------------------------------------------------------------
# Validation and Default Value Edge Cases
# -----------------------------------------------------------------------


def test_base_response_validation():
    """Test that BaseResponse validates execution_status correctly."""
    # Invalid status should raise ValidationError
    with pytest.raises(ValidationError, match="Input should be 'success' or 'error'"):
        _ = BaseResponse(execution_status="pending")  # type: ignore

    # Default execution_message is provided
    resp = BaseResponse(execution_status="success")
    assert resp.execution_message == "Execution completed successfully."
    assert resp.execution_status == "success"


def test_list_calendar_events_request_defaults():
    req = ListCalendarEventsRequest()
    assert req.max_events == 10
    assert req.date_min is None
    assert req.query is None


def test_list_meet_sessions_response_echo():
    """Test that creating a response requires the inherited request fields."""
    # missing meeting_code
    with pytest.raises(ValidationError, match="meeting_code"):
        _ = ListMeetSessionsResponse(execution_status="error")

    # valid creation
    resp = ListMeetSessionsResponse(
        execution_status="success", meeting_code="abc-123-xyz"
    )
    assert resp.meeting_code == "abc-123-xyz"
    assert resp.sessions == []  # default_factory validates correctly


def test_get_meet_recording_nullability():
    """Test that nullable properties accept None."""
    resp = GetMeetRecordingResponse(
        execution_status="success", recording_id="rec-123", recording=None
    )
    assert resp.recording is None
    assert resp.recording_id == "rec-123"
