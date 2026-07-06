import pytest
from pydantic import ValidationError
from mcp_servers.outlook.app.schemas import (
    ListCalendarEventsRequest,
    DownloadableFiles,
)


def test_list_calendar_events_request_validation():
    # Happy Path
    req = ListCalendarEventsRequest(
        date_min="2024-01-01",
        date_max="2024-01-02",
        time_min="00:00:00Z",
        time_max="23:59:59Z",
    )
    assert req.date_min == "2024-01-01"

    # Edge Case: Both dates provided without time is valid
    req2 = ListCalendarEventsRequest(
        date_min="2024-01-01",
        date_max="2024-01-02",
    )
    assert req2.time_min is None

    # Failure Mode: time without dates
    with pytest.raises(ValidationError, match="Dates \\(date_min and date_max\\) are required"):
        ListCalendarEventsRequest(time_min="00:00:00Z")

    # Failure Mode: only one date
    with pytest.raises(ValidationError, match="Both date_min and date_max are required"):
        ListCalendarEventsRequest(date_min="2024-01-01")


def test_downloadable_files_enum():
    # Happy Path
    assert DownloadableFiles("application/pdf") == DownloadableFiles.PDF
    
    # Failure Mode
    with pytest.raises(ValueError):
        DownloadableFiles("text/plain")
