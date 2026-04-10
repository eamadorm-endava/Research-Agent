from typing import Annotated
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import StrEnum


class Scopes(StrEnum):
    """Enumeration of required Google Calendar and Meet API scopes."""

    CALENDAR_READONLY = "https://www.googleapis.com/auth/calendar.events.readonly"
    MEET_READONLY = "https://www.googleapis.com/auth/meetings.space.readonly"


class CalendarMcpConfigBase(BaseSettings):
    """Shared immutable configuration base for the Calendar MCP server.
    Ensures consistent Pydantic settings across all configuration models.
    """

    model_config = SettingsConfigDict(
        extra="forbid",
        frozen=True,
        env_file_encoding="utf-8",
    )


class CalendarAPIConfig(CalendarMcpConfigBase):
    """Configuration for Google Calendar/Meet API scopes and authentication endpoints.
    Defines the default set of scopes needed for operation and OAuth endpoints.
    """

    required_scopes: Annotated[
        tuple[Scopes, ...],
        Field(
            default=(Scopes.CALENDAR_READONLY, Scopes.MEET_READONLY),
            description=(
                "Full set of scopes required for the Calendar MCP server. "
                "Defined as a tuple to ensure global config immutability."
            ),
        ),
    ]
    google_token_info_url: Annotated[
        str,
        Field(
            default="https://oauth2.googleapis.com/tokeninfo",
            description="Google OAuth2 token info endpoint.",
        ),
    ]
    google_accounts_issuer_url: Annotated[
        str,
        Field(
            default="https://accounts.google.com",
            description="Google Accounts issuer URL.",
        ),
    ]


class CalendarServerConfig(BaseSettings):
    """Configuration for the MCP server's network and operational settings.
    Binds the server to the specific host, port, and behavior (stateless, JSON).
    """

    server_name: Annotated[
        str,
        Field(
            default="google-calendar-mcp-server",
            description="Published name of the Calendar MCP server.",
        ),
    ]
    default_host: Annotated[
        str,
        Field(
            default="0.0.0.0",
            description="Default interface the Calendar MCP server binds to.",
        ),
    ]
    default_port: Annotated[
        int,
        Field(
            default=8080,
            ge=1,
            le=65535,
            description="Default port for the Calendar MCP server (from registry).",
        ),
    ]
    default_log_level: Annotated[
        str,
        Field(
            default="INFO",
            description="Default log level for the local Calendar MCP server.",
        ),
    ]
    stateless_http: Annotated[
        bool,
        Field(
            default=True,
            description="Whether the server should use stateless HTTP mode.",
        ),
    ]
    json_response: Annotated[
        bool,
        Field(
            default=True,
            description="Whether the MCP server should use JSON responses.",
        ),
    ]
    debug: Annotated[
        bool,
        Field(
            default=False,
            description="Whether the Starlette app should run in debug mode.",
        ),
    ]


CALENDAR_API_CONFIG = CalendarAPIConfig()
CALENDAR_SERVER_CONFIG = CalendarServerConfig()
