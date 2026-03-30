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


class GoogleAPIsConfig(MeetMcpConfigBase):
    """Configuration for Google Meet API defaults and pagination."""

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


GOOGLE_APIS_CONFIG = GoogleAPIsConfig()
