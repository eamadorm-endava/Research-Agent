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


class AgentDependencies(BaseModel):
    app_name: Annotated[
        str,
        Field(
            description="The name of the calling application or agent.",
        ),
    ]
    user_id: Annotated[
        str,
        Field(
            description="The unique identifier of the user using the agent",
        ),
    ]
    session_id: Annotated[
        str,
        Field(
            description="The current session or conversation ID with the agent",
        ),
    ]


class BaseRequest(BaseModel):
    dependencies: Annotated[
        Optional[AgentDependencies],
        Field(
            default=None,
            exclude=True,
            description=(
                """
                Parameters that needs to be injected by the framework. The LLM will not see this parameters due to exclude = True to avoid LLM hallucinations.
                """
            ),
        ),
    ]

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        """
        Removes the dependencies field from the generated JSON Schema to prevent LLM hallucinations.

        Args:
            core_schema: Any -> The core Pydantic schema being processed.
            handler: Any -> The schema generation handler.

        Returns:
            dict -> The modified JSON Schema dictionary.
        """
        json_schema = super().__get_pydantic_json_schema__(core_schema, handler)
        json_schema = handler.resolve_ref_schema(json_schema)
        if "properties" in json_schema and "dependencies" in json_schema["properties"]:
            json_schema["properties"].pop("dependencies")
        return json_schema


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


class ListCalendarEventsRequest(BaseRequest):
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
    server_current_time_utc: Annotated[
        Optional[str],
        Field(
            default=None,
            description="The current server time in UTC format. Use this along with event timezones to group events into 'Past' or 'Future'.",
        ),
    ]
    events: Annotated[
        list[CalendarEvent],
        Field(
            default_factory=list,
        ),
    ]


class ListMeetSessionsRequest(BaseRequest):
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


class ListMeetParticipantsRequest(BaseRequest):
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


class GetMeetRecordingRequest(BaseRequest):
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


class GetMeetTranscriptRequest(BaseRequest):
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
