from typing import Annotated, Literal, Optional, Self
from pydantic import BaseModel, Field, model_validator

from .calendar.schemas import CalendarEvent
from .meet.schemas import MeetParticipant, MeetRecording, MeetSession, MeetTranscript


# Reusable Type Aliases
DateFilterType = Annotated[
    Optional[str],
    Field(
        default=None,
        description="Date filter in YYYY-MM-DD format.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
]

TimeFilterType = Annotated[
    Optional[str],
    Field(
        default=None,
        description="Time filter in HH:MM:SSZ or HH:MM:SS[+-]HH:MM format.",
        pattern=r"^\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$",
    ),
]


class BaseResponse(BaseModel):
    """
    Base response model for all Google Calendar and Meet tools.
    """

    execution_status: Annotated[
        Literal["success", "error"],
        Field(
            description="The status of the execution.",
        ),
    ]
    execution_message: Annotated[
        str,
        Field(
            default="Execution completed successfully.",
            description="Detailed message about the execution or error description.",
        ),
    ]


class ListCalendarEventsRequest(BaseModel):
    """
    Request schema for listing calendar events with optional time filters.
    """

    max_events: Annotated[
        int,
        Field(
            default=30,
            description="The maximum number of events to return.",
        ),
    ]
    date_min: DateFilterType
    time_min: TimeFilterType
    date_max: DateFilterType
    time_max: TimeFilterType
    sort_order: Annotated[
        Optional[Literal["asc", "desc"]],
        Field(
            default="asc",
            description="The direction of sorting. 'asc' for ascending, 'desc' for descending (newest first).",
        ),
    ]
    query: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Free text search terms to find events. Matches are found across multiple fields "
                "including the event summary (title), description, location, organizer, and attendees. "
                "Examples: 'AI architecture sync' or 'jane.doe@example.com'."
            ),
        ),
    ]

    @model_validator(mode="after")
    def validate_time_filters(self) -> Self:
        """
        Ensures temporal logic consistency between date and time parameters.

        Args:
            self: The model instance.

        Returns:
            Self: The validated model.
        """
        # Time without Date: Raise error if times are provided but dates are missing
        if (self.time_min or self.time_max) and (
            not self.date_min or not self.date_max
        ):
            raise ValueError(
                "Dates (date_min and date_max) are required when using time filters."
            )

        # Mandatory Date Pair: Raise error if only one date filter is provided
        if bool(self.date_min) != bool(self.date_max):
            raise ValueError(
                "Both date_min and date_max are required for a valid date-time search range."
            )

        return self


class ListCalendarEventsResponse(BaseResponse):
    events: Annotated[
        list[CalendarEvent],
        Field(
            default_factory=list,
        ),
    ]


class ListMeetSessionsRequest(BaseModel):
    meeting_code: Annotated[
        str,
        Field(
            description="The 10-letter Google Meet code (e.g., 'abc-defg-hij').",
        ),
    ]


class ListMeetSessionsResponse(BaseResponse, ListMeetSessionsRequest):
    sessions: Annotated[
        list[MeetSession],
        Field(
            default_factory=list,
        ),
    ]


class ListMeetParticipantsRequest(BaseModel):
    meet_session_id: Annotated[
        str,
        Field(
            description="Unique Meet session ID (e.g., 'conferenceRecords/abc-123-xyz').",
        ),
    ]


class ListMeetParticipantsResponse(BaseResponse, ListMeetParticipantsRequest):
    participants: Annotated[
        list[MeetParticipant],
        Field(
            default_factory=list,
        ),
    ]


class GetMeetRecordingRequest(BaseModel):
    recording_id: Annotated[
        str,
        Field(
            description="The unique recording ID.",
        ),
    ]


class GetMeetRecordingResponse(BaseResponse, GetMeetRecordingRequest):
    recording: Annotated[
        Optional[MeetRecording],
        Field(
            default=None,
        ),
    ]


class GetMeetTranscriptRequest(BaseModel):
    transcript_id: Annotated[
        str,
        Field(
            description="The canonical resource ID of the transcript.",
        ),
    ]


class GetMeetTranscriptResponse(BaseResponse, GetMeetTranscriptRequest):
    transcript: Annotated[
        Optional[MeetTranscript],
        Field(
            default=None,
        ),
    ]
