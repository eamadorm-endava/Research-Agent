from typing import Annotated
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


class RootConfig(BaseSettings):
    """Shared immutable configuration base for the Calendar MCP server."""

    model_config = SettingsConfigDict(
        extra="forbid",
        frozen=True,
        env_file_encoding="utf-8",
    )


class CalendarConfig(RootConfig):
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
    order_by: Annotated[
        str,
        Field(
            default="startTime",
            description="Determines if events are sorted by 'startTime' or 'updated' time.",
        ),
    ]
    duration_format: Annotated[
        str,
        Field(
            default="{hours}h {minutes}m {seconds}s",
            description="Format string for displaying event durations.",
        ),
    ]


CALENDAR_CONFIG = CalendarConfig()
