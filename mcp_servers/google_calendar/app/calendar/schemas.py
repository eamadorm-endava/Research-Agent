from loguru import logger
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Optional
from pydantic import BaseModel, Field, computed_field, field_serializer, field_validator
from dateutil import parser


# The different values and attributes for the schemas below were obtained from:
# https://developers.google.com/workspace/calendar/api/v3/reference/events


class EventStatus(StrEnum):
    """Available status values for a calendar event from the API."""

    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class ResponseStatus(StrEnum):
    """Available response status values for an attendee from the API."""

    NEEDS_ACTION = "needsAction"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    ACCEPTED = "accepted"


class ConferenceData(BaseModel):
    """Information regarding a conference associated with an event."""

    joining_url: Annotated[str, Field(description="URL to join the conference.")]
    conference_id: Annotated[str, Field(description="Unique ID of the conference.")]


class Attendee(BaseModel):
    """Metadata for an attendee or organizer in a calendar event."""

    email: Annotated[str, Field(description="Email address of the attendee.")]
    display_name: Annotated[
        Optional[str], Field(default=None, description="Display name of the attendee.")
    ]
    response_status: Annotated[
        ResponseStatus,
        Field(
            default=ResponseStatus.NEEDS_ACTION,
            description="The attendee's response status.",
        ),
    ]
    organizer: Annotated[
        bool,
        Field(default=False, description="Whether this attendee is the organizer."),
    ]
    optional: Annotated[
        bool,
        Field(
            default=False, description="Whether this attendee is an optional attendee."
        ),
    ]


class EventAttachment(BaseModel):
    """Metadata for a file attached to a calendar event."""

    file_id: Annotated[
        Optional[str],
        Field(default=None, description="The Google Drive ID of the attached file."),
    ]
    file_url: Annotated[str, Field(description="The URL link to the attachment.")]
    title: Annotated[
        Optional[str], Field(default=None, description="The title of the attachment.")
    ]
    mime_type: Annotated[
        Optional[str],
        Field(default=None, description="The MIME type of the attachment."),
    ]


class CalendarEvent(BaseModel):
    """Represents the output structure of a Google Calendar event from the API."""

    event_id: Annotated[str, Field(description="The unique identifier for the event.")]
    title: Annotated[
        Optional[str], Field(default=None, description="Title of the calendar event.")
    ]
    description: Annotated[
        Optional[str],
        Field(default=None, description="Description of the calendar event."),
    ]
    event_status: Annotated[
        Optional[EventStatus],
        Field(default=None, description="The status of the event."),
    ]

    start_time: Annotated[
        datetime,
        Field(
            description="Start time of the event as a datetime object (e.g. '2023-10-27T10:00:00Z')."
        ),
    ]
    end_time: Annotated[
        datetime,
        Field(
            description="End time of the event as a datetime object (e.g. '2023-10-27T11:30:00Z')."
        ),
    ]

    attendees: Annotated[
        list[Attendee],
        Field(
            default_factory=list, description="List of attendees invited to the event."
        ),
    ]
    conference_info: Annotated[
        list[ConferenceData],
        Field(
            default_factory=list,
            description="List of conference data associated with the event.",
        ),
    ]
    attachments: Annotated[
        list[EventAttachment],
        Field(default_factory=list, description="List of files attached to the event."),
    ]

    @computed_field
    @property
    def duration(self) -> str:
        """Calculate the duration between start_time and end_time in Hh Mm format.

        Return:
            A string formatted as "Xh Ym".
        """
        delta = self.end_time - self.start_time
        seconds = int(delta.total_seconds())
        hours, remainder = divmod(seconds, 3600)
        minutes = remainder // 60
        return f"{hours}h {minutes}m"

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def parse_datetime(cls, value: Any) -> Optional[datetime]:
        """Convert a string representation of time to a datetime object.

        Args:
            value (Any): The string or datetime value to parse.

        Return:
            A datetime object or None if parsing fails.
        """
        if isinstance(value, str):
            try:
                return parser.isoparse(value)
            except ValueError as e:
                logger.error(f"Failed to parse datetime string '{value}': {e}")
                return None

        if value is None or isinstance(value, datetime):
            return value

        logger.warning(
            f"Unexpected type for datetime field: {type(value)}. Expected string or datetime."
        )
        return None

    @field_serializer("start_time", "end_time")
    def serialize_datetime(self, dt: datetime) -> str:
        """Serialize a datetime object to an ISO 8601 string containing the timezone.

        Args:
            dt (datetime): The datetime object to serialize.

        Return:
            An ISO 8601 string as the serialized representation.
        """
        serialized = dt.isoformat()
        logger.debug(f"Serialized datetime {dt} to '{serialized}'")
        return serialized
