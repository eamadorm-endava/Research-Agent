from unittest.mock import MagicMock, patch
import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response as Httplib2Response

from mcp_servers.google_calendar.app.calendar.calendar_client import CalendarClient

# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture
def mock_build():
    with patch(
        "mcp_servers.google_calendar.app.calendar.calendar_client.build"
    ) as mock:
        yield mock


@pytest.fixture
def calendar_client(mock_build):
    return CalendarClient(MagicMock())


def _make_http_error(status_code: int) -> HttpError:
    resp = Httplib2Response({"status": status_code})
    return HttpError(resp=resp, content=b"error")


# -----------------------------------------------------------------------
# format_time_filters Logic
# -----------------------------------------------------------------------


def test_format_time_filters_missing_dates_raises(calendar_client):
    # Time provided but dates missing
    with pytest.raises(ValueError, match="Dates .* are required"):
        calendar_client._format_time_filters(time_min="10:00:00Z")


def test_format_time_filters_only_one_date_raises(calendar_client):
    # Only date_min provided
    with pytest.raises(ValueError, match="Both date_min and date_max are required"):
        calendar_client._format_time_filters(date_min="2024-01-01")


def test_format_time_filters_success(calendar_client):
    result = calendar_client._format_time_filters(
        date_min="2024-01-01",
        time_min="10:00:00Z",
        date_max="2024-01-01",
        time_max="11:00:00Z",
    )
    assert result["formatted_time_min"] == "2024-01-01T10:00:00Z"
    assert result["formatted_time_max"] == "2024-01-01T11:00:00Z"


def test_format_time_filters_global_search(calendar_client):
    result = calendar_client._format_time_filters()
    assert result["formatted_time_min"] is None
    assert result["formatted_time_max"] is None


# -----------------------------------------------------------------------
# list_events Execution
# -----------------------------------------------------------------------


def test_list_events_api_failure_returns_empty(calendar_client, mock_build):
    mock_calendar = mock_build.return_value
    mock_calendar.events.return_value.list.return_value.execute.side_effect = (
        _make_http_error(500)
    )

    events = calendar_client.list_events(max_events=10)
    assert events == []


def test_list_events_success(calendar_client, mock_build):
    mock_calendar = mock_build.return_value
    mock_calendar.events.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "event-1",
                "summary": "Meeting",
                "status": "confirmed",
                "start": {"dateTime": "2024-01-01T10:00:00Z"},
                "end": {"dateTime": "2024-01-01T11:00:00Z"},
            }
        ]
    }

    events = calendar_client.list_events(max_events=1)
    assert len(events) == 1
    assert events[0].title == "Meeting"
    assert events[0].event_id == "event-1"


# -----------------------------------------------------------------------
# Parsing Edge Cases
# -----------------------------------------------------------------------


def test_parse_attendees_incomplete_data(calendar_client):
    raw_attendees = [{"email": "test@example.com"}]  # Missing id, displayName, etc.
    organizer = {}

    attendees = calendar_client._parse_attendees(raw_attendees, organizer)
    assert len(attendees) == 1
    assert attendees[0].email == "test@example.com"
    assert attendees[0].display_name is None


def test_parse_conference_data_unrecognized_entry(calendar_client):
    conf_data = {
        "conferenceId": "abc-123",
        "entryPoints": [{"type": "other"}],  # Missing uri
    }
    result = calendar_client._parse_conference_data(conf_data)
    assert result == []


def test_parse_conference_data_success(calendar_client):
    conf_data = {
        "conferenceId": "abc-123",
        "entryPoints": [{"uri": "https://meet.google.com/abc-123", "type": "video"}],
    }
    result = calendar_client._parse_conference_data(conf_data)
    assert len(result) == 1
    assert result[0].joining_url == "https://meet.google.com/abc-123"
    assert result[0].conference_id == "abc-123"
