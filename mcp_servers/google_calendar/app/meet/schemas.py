from loguru import logger
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator
from dateutil import parser
from ..utils import calculate_duration


class MeetBase(BaseModel):
    """Shared schema base for the Google Meet module."""

    model_config = ConfigDict(
        extra="forbid",
    )


class UserType(StrEnum):
    """Types of participants in a Meet session."""

    SIGNED_IN = "SIGNED_IN"
    ANONYMOUS = "ANONYMOUS"
    PHONE = "PHONE"


class ArtifactStatus(StrEnum):
    """Common states for recordings and transcripts."""

    STATE_UNSPECIFIED = "STATE_UNSPECIFIED"
    STARTED = "STARTED"
    ENDED = "ENDED"
    FILE_GENERATED = "FILE_GENERATED"


# --- Atomic Details (Low-Level) ---


class MeetParticipant(MeetBase):
    """Detailed metadata for a participant in a Meet session."""

    user_id: Annotated[
        str,
        Field(description="Unique Google resource name of the user (e.g., users/123)."),
    ]
    email: Annotated[
        Optional[str],
        Field(default=None, description="User's email address (if available)."),
    ]
    display_name: Annotated[
        str,
        Field(description="Visible name of the participant."),
    ]
    first_join_time: Annotated[
        datetime,
        Field(description="First time the participant joined."),
    ]
    last_leave_time: Annotated[
        datetime,
        Field(description="Last time the participant left."),
    ]
    user_type: Annotated[
        UserType,
        Field(description="Type of user (SIGNED_IN, ANONYMOUS, PHONE)."),
    ]

    @field_validator("first_join_time", "last_leave_time", mode="before")
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

    @computed_field
    @property
    def time_in_meeting(self) -> str:
        """Calculate the duration of the participant's presence in Xh Ym Zs format.

        Return:
            A string formatted as "Xh Ym Zs".
        """
        return calculate_duration(self.first_join_time, self.last_leave_time)


class MeetRecording(MeetBase):
    """Detailed metadata for a media recording artifact."""

    recording_id: Annotated[
        str,
        Field(description="Unique resource name of the recording."),
    ]
    state: Annotated[
        ArtifactStatus,
        Field(description="Current status of the recording."),
    ]
    drive_file_id: Annotated[
        Optional[str],
        Field(default=None, description="Google Drive ID of the MP4 file."),
    ]
    start_time: Annotated[
        datetime,
        Field(description="Actual start time of the recording."),
    ]
    end_time: Annotated[
        datetime,
        Field(description="Actual end time of the recording."),
    ]

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

    @computed_field
    @property
    def recording_url(self) -> Optional[str]:
        """Direct URL to view the recording file in Google Drive."""
        if not self.drive_file_id:
            return None
        return f"https://drive.google.com/file/d/{self.drive_file_id}/view"

    @computed_field
    @property
    def duration(self) -> str:
        """Calculate the duration of the recording in Xh Ym Zs format.

        Return:
            A string formatted as "Xh Ym Zs".
        """
        return calculate_duration(self.start_time, self.end_time)


class MeetTranscript(MeetBase):
    """Detailed metadata for a transcript artifact."""

    transcript_id: Annotated[
        str,
        Field(description="Unique resource name of the transcript."),
    ]
    state: Annotated[
        ArtifactStatus,
        Field(description="Current status of the transcript."),
    ]
    docs_document_id: Annotated[
        Optional[str],
        Field(default=None, description="Google Docs ID of the transcript."),
    ]
    start_time: Annotated[
        datetime,
        Field(description="Actual start time of the transcript."),
    ]
    end_time: Annotated[
        datetime,
        Field(description="Actual end time of the transcript."),
    ]

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

    @computed_field
    @property
    def transcript_url(self) -> Optional[str]:
        """Direct URL to edit/view the transcript in Google Docs."""
        if not self.docs_document_id:
            return None
        return f"https://docs.google.com/document/d/{self.docs_document_id}/edit"

    @computed_field
    @property
    def duration(self) -> str:
        """Calculate the duration of the transcript in Xh Ym Zs format.

        Return:
            A string formatted as "Xh Ym Zs".
        """
        return calculate_duration(self.start_time, self.end_time)


# --- Metadata Summaries ---


class MeetRecordingsSummary(MeetBase):
    """High-level summary of recordings in a session."""

    total_recordings: Annotated[
        int,
        Field(description="Total number of recordings found."),
    ]
    recording_ids: Annotated[
        list[str],
        Field(default_factory=list, description="List of recording resource names."),
    ]


class MeetTranscriptsSummary(MeetBase):
    """High-level summary of transcripts in a session."""

    total_transcripts: Annotated[
        int,
        Field(description="Total number of transcripts found."),
    ]
    transcript_ids: Annotated[
        list[str],
        Field(default_factory=list, description="List of transcript resource names."),
    ]


# --- Top-Level View ---


class MeetSession(MeetBase):
    """Summary of a single Google Meet session (Meet session record)."""

    meeting_code: Annotated[
        str,
        Field(
            description="The 10-letter meeting code (e.g., abc-defg-hij) used to access the session."
        ),
    ]
    session_id: Annotated[
        str,
        Field(description="Unique resource name of the specific timed occurrence."),
    ]
    start_time: Annotated[
        datetime,
        Field(description="Session start time."),
    ]
    end_time: Annotated[
        datetime,
        Field(description="Session end time."),
    ]
    total_participants: Annotated[
        int,
        Field(description="Total number of unique participants."),
    ]
    recordings: Annotated[
        MeetRecordingsSummary,
        Field(description="Summary of recordings."),
    ]
    transcripts: Annotated[
        MeetTranscriptsSummary,
        Field(description="Summary of transcripts."),
    ]

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

    @computed_field
    @property
    def duration(self) -> str:
        """Calculate the duration of the session in Xh Ym Zs format.

        Return:
            A string formatted as "Xh Ym Zs".
        """
        return calculate_duration(self.start_time, self.end_time)
