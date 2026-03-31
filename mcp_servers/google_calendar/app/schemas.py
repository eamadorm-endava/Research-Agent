from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


class AuthenticationError(Exception):
    """Raised when the Google API returns a 401 or 403 status code."""

    pass


class MeetApiQuotaError(Exception):
    """Raised when the Google API returns a 429 (quota exceeded) status code."""

    pass


class MeetSchemaModel(BaseModel):
    """Shared schema base for the Google Meet MCP server."""

    model_config = ConfigDict(extra="forbid")


class DriveDestinationModel(MeetSchemaModel):
    """Drive file reference for a recording artifact."""

    file: Annotated[
        Optional[str],
        Field(default=None, description="Drive file ID of the recording."),
    ]
    exportUri: Annotated[
        Optional[str],
        Field(default=None, description="URI to export/download the recording."),
    ]


class DocsDestinationModel(MeetSchemaModel):
    """Docs file reference for a transcript artifact."""

    document: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Google Docs resource name for the transcript document.",
        ),
    ]
    exportUri: Annotated[
        Optional[str],
        Field(default=None, description="URI to export/download the transcript."),
    ]


class SignedInUserModel(MeetSchemaModel):
    """Authenticated user identity from the People API surface."""

    user: Annotated[
        Optional[str],
        Field(
            default=None,
            description="People API resource name, e.g. 'users/123456'.",
        ),
    ]
    displayName: Annotated[
        Optional[str],
        Field(default=None, description="Display name of the participant."),
    ]


class ConferenceRecordModel(MeetSchemaModel):
    """Metadata for a single Google Meet conference record.

    The ``title`` field is enriched from the linked Google Calendar event
    and is not part of the Meet API response itself.
    """

    name: Annotated[
        str,
        Field(
            description=(
                "Resource name in the format 'conferenceRecords/{conferenceRecord}'."
            ),
        ),
    ]
    title: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Calendar event title for this conference, enriched from "
                "the Google Calendar API. May be None for ad-hoc meetings."
            ),
        ),
    ]
    description: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Calendar event description for this conference, enriched from "
                "the Google Calendar API. May be None for ad-hoc meetings."
            ),
        ),
    ]
    startTime: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Conference start time in RFC 3339 format.",
        ),
    ]
    endTime: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Conference end time in RFC 3339 format.",
        ),
    ]
    space: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Resource name of the meeting space.",
        ),
    ]
    expireTime: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Expiration time of the conference record in RFC 3339 format.",
        ),
    ]


class RecordingModel(MeetSchemaModel):
    """Metadata for a recording associated with a conference record."""

    name: Annotated[
        str,
        Field(
            description=(
                "Resource name in the format "
                "'conferenceRecords/{conferenceRecord}/recordings/{recording}'."
            ),
        ),
    ]
    state: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Recording state, e.g. 'STARTED', 'ENDED', 'FILE_GENERATED'.",
        ),
    ]
    startTime: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Recording start time in RFC 3339 format.",
        ),
    ]
    endTime: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Recording end time in RFC 3339 format.",
        ),
    ]
    driveDestination: Annotated[
        Optional[DriveDestinationModel],
        Field(
            default=None,
            description="Drive file reference for the MP4 recording.",
        ),
    ]


class TranscriptModel(MeetSchemaModel):
    """Metadata for a transcript associated with a conference record."""

    name: Annotated[
        str,
        Field(
            description=(
                "Resource name in the format "
                "'conferenceRecords/{conferenceRecord}/transcripts/{transcript}'."
            ),
        ),
    ]
    state: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Transcript state, e.g. 'STARTED', 'ENDED', 'FILE_GENERATED'.",
        ),
    ]
    startTime: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Transcript start time in RFC 3339 format.",
        ),
    ]
    endTime: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Transcript end time in RFC 3339 format.",
        ),
    ]
    docsDestination: Annotated[
        Optional[DocsDestinationModel],
        Field(
            default=None,
            description="Google Docs reference for the full transcript document.",
        ),
    ]


class TranscriptEntryModel(MeetSchemaModel):
    """A single spoken segment within a transcript."""

    name: Annotated[
        str,
        Field(
            description=(
                "Resource name in the format "
                "'conferenceRecords/{conferenceRecord}/"
                "transcripts/{transcript}/entries/{entry}'."
            ),
        ),
    ]
    participant: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Resource name of the participant who spoke, e.g. "
                "'conferenceRecords/{conferenceRecord}/participants/{participant}'."
            ),
        ),
    ]
    text: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Transcribed text of the participant's speech.",
        ),
    ]
    languageCode: Annotated[
        Optional[str],
        Field(
            default=None,
            description="BCP-47 language code, e.g. 'en-US'.",
        ),
    ]
    startTime: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Entry start time in RFC 3339 format.",
        ),
    ]
    endTime: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Entry end time in RFC 3339 format.",
        ),
    ]


class ParticipantModel(MeetSchemaModel):
    """Metadata for a participant in a conference record."""

    name: Annotated[
        str,
        Field(
            description=(
                "Resource name in the format "
                "'conferenceRecords/{conferenceRecord}/"
                "participants/{participant}'."
            ),
        ),
    ]
    earliestStartTime: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Earliest join time across all sessions, RFC 3339 format.",
        ),
    ]
    latestEndTime: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Latest leave time across all sessions, RFC 3339 format.",
        ),
    ]
    signedinUser: Annotated[
        Optional[SignedInUserModel],
        Field(
            default=None,
            description="Signed-in user identity (display name and People API ref).",
        ),
    ]
