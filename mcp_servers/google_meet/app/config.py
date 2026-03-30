from __future__ import annotations

from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


class MeetMcpConfigBase(BaseSettings):
    """Shared immutable configuration base for the Meet MCP server."""

    model_config = SettingsConfigDict(
        extra="forbid",
        frozen=True,
        env_file_encoding="utf-8",
    )


class DriveConfig(MeetMcpConfigBase):
    """Configuration for Google Drive API."""

    drive_api_service_name: Annotated[
        str,
        Field(
            default="drive",
            description="Google API discovery service name for Drive.",
        ),
    ]
    drive_api_version: Annotated[
        str,
        Field(
            default="v3",
            description="Google Drive API version used to resolve recording files.",
        ),
    ]


class MeetConfig(MeetMcpConfigBase):
    """Configuration for Google Meet API and defaults."""

    meet_api_service_name: Annotated[
        str,
        Field(
            default="meet",
            description="Google API discovery service name for Meet.",
        ),
    ]
    meet_api_version: Annotated[
        str,
        Field(
            default="v2",
            description="Google Meet API version.",
        ),
    ]
    default_page_size: Annotated[
        int,
        Field(
            default=DEFAULT_PAGE_SIZE,
            ge=1,
            le=MAX_PAGE_SIZE,
            description="Default number of items returned per page.",
        ),
    ]
    max_page_size: Annotated[
        int,
        Field(
            default=MAX_PAGE_SIZE,
            ge=1,
            le=1000,
            description="Maximum allowed page size for list operations.",
        ),
    ]
    space_name_prefix: Annotated[
        str,
        Field(
            default="spaces/",
            description="Prefix used for Google Meet space resource names.",
        ),
    ]


class CalendarConfig(MeetMcpConfigBase):
    """Configuration for Google Calendar API and search settings."""

    calendar_api_service_name: Annotated[
        str,
        Field(
            default="calendar",
            description="Google API discovery service name for Calendar.",
        ),
    ]
    calendar_api_version: Annotated[
        str,
        Field(
            default="v3",
            description="Google Calendar API version used to resolve event titles.",
        ),
    ]
    calendar_id: Annotated[
        str,
        Field(
            default="primary",
            description="The calendar ID to search for meetings.",
        ),
    ]
    max_calendar_search_results: Annotated[
        int,
        Field(
            default=100,
            ge=1,
            le=250,
            description="Maximum number of Calendar events to search through.",
        ),
    ]
    default_start_time: Annotated[
        str,
        Field(
            default="00:00:00Z",
            description="Default start time if only date is provided.",
        ),
    ]
    default_end_time: Annotated[
        str,
        Field(
            default="23:59:59Z",
            description="Default end time if only date is provided.",
        ),
    ]
    meet_url_prefix: Annotated[
        str,
        Field(
            default="meet.google.com/",
            description="Prefix used to identify Meet URLs in Calendar events.",
        ),
    ]
    video_entry_point: Annotated[
        str,
        Field(
            default="video",
            description="Entry point type to look for in Calendar conference data.",
        ),
    ]


DRIVE_CONFIG = DriveConfig()
MEET_CONFIG = MeetConfig()
CALENDAR_CONFIG = CalendarConfig()
