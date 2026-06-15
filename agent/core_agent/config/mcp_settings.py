from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, AliasChoices
from typing import Annotated, Optional, Union

from .oauth_settings import BaseOAuthConfig


class BaseMCPConfig(BaseSettings):
    """Generic MCP server configuration base class inherited by each server-specific config."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
    )

    GENERAL_TIMEOUT: Annotated[
        int,
        Field(
            default=60,
            description="Timeout in seconds for MCP servers.",
        ),
    ]
    OAUTH_CONFIG: Annotated[
        Optional[BaseOAuthConfig],
        Field(
            default=None,
            description="The OAuth 2.0 configuration for this MCP server.",
        ),
    ]
    OAUTH_SCOPES: Annotated[
        Union[dict[str, str], list[str]],
        Field(
            default_factory=list,
            description="OAuth scopes requested by the agent.",
        ),
    ]
    GEMINI_AUTH_ID: Annotated[
        Optional[str],
        Field(
            default=None,
            description="The ID of the shared delegated OAuth authorization resource registered in Gemini Enterprise.",
        ),
    ]
    URL: Annotated[
        str,
        Field(
            default="http://localhost",
            description="The URL for the MCP server.",
        ),
    ]
    ENDPOINT: Annotated[
        str,
        Field(
            default="/mcp",
            description="The endpoint for the MCP server.",
        ),
    ]

    @field_validator("OAUTH_SCOPES", mode="after")
    @classmethod
    def validate_oauth_scopes(
        cls, v: Union[list[str], dict[str, str]]
    ) -> dict[str, str]:
        """
        Normalises OAUTH_SCOPES from a list of scopes to the dict format.

        Args:
            v: Union[list[str], dict[str, str]] -> Raw field value: either already a dict or a list of scopes.

        Returns:
            dict[str, str] -> Scope URL to description mapping required by McpToolset.
        """
        if isinstance(v, dict):
            return v
        description = f"{cls.__name__.replace('MCPConfig', '').lower()} access"
        return {scope: description for scope in v}


class BigQueryMCPConfig(BaseMCPConfig):
    """Configuration for the BigQuery MCP server."""

    model_config = SettingsConfigDict(env_prefix="BIGQUERY_")

    URL: str = "http://localhost:8080"
    OAUTH_SCOPES: Union[dict[str, str], list[str]] = [
        "https://www.googleapis.com/auth/bigquery"
    ]
    GEMINI_AUTH_ID: Annotated[
        Optional[str],
        Field(
            default="mock-ge-auth-id",
            description="Auth Resource ID for BigQuery.",
            validation_alias=AliasChoices(
                "BIGQUERY_AUTH_ID",
                "GEMINI_GOOGLE_AUTH_ID",
            ),
        ),
    ]


class DriveMCPConfig(BaseMCPConfig):
    """Configuration for the Google Drive MCP server."""

    model_config = SettingsConfigDict(env_prefix="DRIVE_")

    URL: str = "http://localhost:8081"
    OAUTH_SCOPES: Union[dict[str, str], list[str]] = [
        "https://www.googleapis.com/auth/drive"
    ]
    GEMINI_AUTH_ID: Annotated[
        Optional[str],
        Field(
            default="mock-ge-auth-id",
            description="Auth Resource ID for Google Drive.",
            validation_alias=AliasChoices(
                "GEMINI_DRIVE_AUTH_ID",
                "GEMINI_GOOGLE_AUTH_ID",
            ),
        ),
    ]


class CalendarMCPConfig(BaseMCPConfig):
    """Configuration for the Google Calendar MCP server."""

    model_config = SettingsConfigDict(env_prefix="CALENDAR_")

    URL: str = "http://localhost:8083"
    OAUTH_SCOPES: Union[dict[str, str], list[str]] = [
        "https://www.googleapis.com/auth/calendar.events.readonly",
        "https://www.googleapis.com/auth/meetings.space.readonly",
    ]
    GEMINI_AUTH_ID: Annotated[
        Optional[str],
        Field(
            default="mock-ge-auth-id",
            description="Auth Resource ID for Google Calendar.",
            validation_alias=AliasChoices("CALENDAR_AUTH_ID", "GEMINI_GOOGLE_AUTH_ID"),
        ),
    ]


class GCSMCPConfig(BaseMCPConfig):
    """Configuration for the Google Cloud Storage MCP server."""

    model_config = SettingsConfigDict(env_prefix="GCS_")

    URL: str = "http://localhost:8082"
    OAUTH_SCOPES: Union[dict[str, str], list[str]] = [
        "https://www.googleapis.com/auth/cloud-platform",
        "openid",
        "email",
    ]
    GEMINI_AUTH_ID: Annotated[
        Optional[str],
        Field(
            default="mock-ge-auth-id",
            description="Auth Resource ID for Google Cloud Storage.",
            validation_alias=AliasChoices(
                "GCS_AUTH_ID",
                "GEMINI_GOOGLE_AUTH_ID",
            ),
        ),
    ]


class OneDriveMCPConfig(BaseMCPConfig):
    """Configuration for the Microsoft OneDrive MCP server."""

    model_config = SettingsConfigDict(env_prefix="ONEDRIVE_")

    URL: str = "http://localhost:8084"
    OAUTH_SCOPES: Union[dict[str, str], list[str]] = [
        "Files.Read.All",
        "Sites.Read.All",
        "offline_access",
    ]
    GEMINI_AUTH_ID: Annotated[
        Optional[str],
        Field(
            default="mock-ms-auth-id",
            description="Auth Resource ID for Microsoft OneDrive.",
            validation_alias=AliasChoices(
                "ONEDRIVE_AUTH_ID",
                "GEMINI_MICROSOFT_AUTH_ID",
            ),
        ),
    ]
