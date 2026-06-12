from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, AliasChoices
from enum import StrEnum
from typing import Annotated, Optional, Union


class DriveScopes(StrEnum):
    """Enum for Google Drive OAuth scopes."""

    DRIVE = "https://www.googleapis.com/auth/drive"


class BigQueryScopes(StrEnum):
    """Enum for Google BigQuery OAuth scopes."""

    BIGQUERY = "https://www.googleapis.com/auth/bigquery"


class CalendarScopes(StrEnum):
    """Enum for Google Calendar OAuth scopes."""

    CALENDAR_READONLY = "https://www.googleapis.com/auth/calendar.events.readonly"
    MEET_READONLY = "https://www.googleapis.com/auth/meetings.space.readonly"


class GCSScopes(StrEnum):
    """Enum for Google Cloud Storage OAuth scopes."""

    CLOUD_PLATFORM = "https://www.googleapis.com/auth/cloud-platform"
    OPENID = "openid"
    EMAIL = "email"


class MicrosoftGraphScopes(StrEnum):
    """Enum for delegated Microsoft Graph OAuth scopes used by Microsoft MCP servers."""

    USER_READ = "User.Read"
    FILES_READ_ALL = "Files.Read.All"
    SITES_READ_ALL = "Sites.Read.All"
    OFFLINE_ACCESS = "offline_access"


class OAuthProvider(StrEnum):
    """Supported OAuth providers for local ADK-managed MCP authentication."""

    GOOGLE = "google"
    MICROSOFT = "microsoft"


def _scopes_to_dict(v: Union[list, dict[str, str]], description: str) -> dict[str, str]:
    """Normalises OAUTH_SCOPES from a list of scope enums to the dict[scope_url, description] format.

    Args:
        v: Union[list, dict[str, str]] -> Raw field value: either already a dict or a list of enums.
        description: str -> Human-readable description assigned to each scope URL.

    Returns:
        dict[str, str] -> Scope URL to description mapping required by McpToolset.
    """
    if isinstance(v, dict):
        return v
    return {scope.value: description for scope in v}


class BaseMCPConfig(BaseSettings):
    """Generic MCP server configuration base class inherited by each server-specific config."""

    model_config = SettingsConfigDict(
        env_file=(".env", "core_agent/.env"),
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
    OAUTH_PROVIDER: Annotated[
        OAuthProvider,
        Field(
            default=OAuthProvider.GOOGLE,
            description=(
                "OAuth provider used by the agent to obtain delegated tokens "
                "for this MCP server during local execution."
            ),
        ),
    ]
    GEMINI_GOOGLE_AUTH_ID: Annotated[
        Optional[str],
        Field(
            default=None,
            description="The ID of the shared delegated Google OAuth authorization resource registered in Gemini Enterprise.",
        ),
    ]

    @property
    def auth_resource_id(self) -> Optional[str]:
        """Returns the delegated OAuth authorization resource ID for this MCP server."""
        return self.GEMINI_GOOGLE_AUTH_ID


class BigQueryMCPConfig(BaseMCPConfig):
    """Configuration for the BigQuery MCP server."""

    URL: Annotated[
        str,
        Field(
            default="http://localhost:8080",
            description="BigQuery MCP Server URL",
            validation_alias="BIGQUERY_URL",
        ),
    ]
    ENDPOINT: Annotated[
        str,
        Field(
            default="/mcp",
            description="BigQuery MCP Server Endpoint",
            validation_alias="BIGQUERY_ENDPOINT",
        ),
    ]
    OAUTH_SCOPES: Annotated[
        Union[dict[str, str], list[BigQueryScopes]],
        Field(
            default=[BigQueryScopes.BIGQUERY],
            description="OAuth scopes requested by the agent.",
            validation_alias="BIGQUERY_OAUTH_SCOPES",
        ),
    ]
    GEMINI_GOOGLE_AUTH_ID: Annotated[
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

    @field_validator("OAUTH_SCOPES", mode="after")
    @classmethod
    def validate_oauth_scopes(
        cls, v: Union[list[BigQueryScopes], dict[str, str]]
    ) -> dict[str, str]:
        return _scopes_to_dict(v, "google bigquery access")


class DriveMCPConfig(BaseMCPConfig):
    """Configuration for the Google Drive MCP server."""

    URL: Annotated[
        str,
        Field(
            default="http://localhost:8081",
            description="Google Drive MCP Server URL",
            validation_alias="DRIVE_URL",
        ),
    ]
    ENDPOINT: Annotated[
        str,
        Field(
            default="/mcp",
            description="Google Drive MCP Server Endpoint",
            validation_alias="DRIVE_ENDPOINT",
        ),
    ]
    OAUTH_SCOPES: Annotated[
        Union[dict[str, str], list[DriveScopes]],
        Field(
            default=[DriveScopes.DRIVE],
            description="OAuth scopes requested by the agent.",
            validation_alias="DRIVE_OAUTH_SCOPES",
        ),
    ]
    GEMINI_GOOGLE_AUTH_ID: Annotated[
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

    @field_validator("OAUTH_SCOPES", mode="after")
    @classmethod
    def validate_oauth_scopes(
        cls, v: Union[list[DriveScopes], dict[str, str]]
    ) -> dict[str, str]:
        return _scopes_to_dict(v, "google drive access")


class CalendarMCPConfig(BaseMCPConfig):
    """Configuration for the Google Calendar MCP server."""

    URL: Annotated[
        str,
        Field(
            default="http://localhost:8083",
            description="Google Calendar MCP Server URL",
            validation_alias="CALENDAR_URL",
        ),
    ]
    ENDPOINT: Annotated[
        str,
        Field(
            default="/mcp",
            description="Google Calendar MCP Server Endpoint",
            validation_alias="CALENDAR_ENDPOINT",
        ),
    ]
    OAUTH_SCOPES: Annotated[
        Union[dict[str, str], list[CalendarScopes]],
        Field(
            default=[
                CalendarScopes.CALENDAR_READONLY,
                CalendarScopes.MEET_READONLY,
            ],
            description="OAuth scopes requested by the agent.",
            validation_alias="CALENDAR_OAUTH_SCOPES",
        ),
    ]
    GEMINI_GOOGLE_AUTH_ID: Annotated[
        Optional[str],
        Field(
            default="mock-ge-auth-id",
            description="Auth Resource ID for Google Calendar.",
            validation_alias=AliasChoices("CALENDAR_AUTH_ID", "GEMINI_GOOGLE_AUTH_ID"),
        ),
    ]

    @field_validator("OAUTH_SCOPES", mode="after")
    @classmethod
    def validate_oauth_scopes(
        cls, v: Union[list[CalendarScopes], dict[str, str]]
    ) -> dict[str, str]:
        return _scopes_to_dict(v, "google calendar access")


class GCSMCPConfig(BaseMCPConfig):
    """Configuration for the Google Cloud Storage MCP server."""

    URL: Annotated[
        str,
        Field(
            default="http://localhost:8082",
            description="GCS MCP Server URL",
            validation_alias="GCS_URL",
        ),
    ]
    ENDPOINT: Annotated[
        str,
        Field(
            default="/mcp",
            description="GCS MCP Server Endpoint",
            validation_alias="GCS_ENDPOINT",
        ),
    ]
    OAUTH_SCOPES: Annotated[
        Union[dict[str, str], list[GCSScopes]],
        Field(
            default=[
                GCSScopes.CLOUD_PLATFORM,
                GCSScopes.OPENID,
                GCSScopes.EMAIL,
            ],
            description="OAuth scopes requested by the agent.",
            validation_alias="GCS_OAUTH_SCOPES",
        ),
    ]
    GEMINI_GOOGLE_AUTH_ID: Annotated[
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

    @field_validator("OAUTH_SCOPES", mode="after")
    @classmethod
    def validate_oauth_scopes(
        cls, v: Union[list[GCSScopes], dict[str, str]]
    ) -> dict[str, str]:
        return _scopes_to_dict(v, "google cloud storage access")


class SharePointMCPConfig(BaseMCPConfig):
    """Configuration for the Microsoft SharePoint MCP server."""

    URL: Annotated[
        str,
        Field(
            default="http://localhost:8084",
            description="SharePoint MCP Server URL",
            validation_alias="SHAREPOINT_URL",
        ),
    ]
    ENDPOINT: Annotated[
        str,
        Field(
            default="/mcp",
            description="SharePoint MCP Server Endpoint",
            validation_alias="SHAREPOINT_ENDPOINT",
        ),
    ]
    OAUTH_PROVIDER: Annotated[
        OAuthProvider,
        Field(
            default=OAuthProvider.MICROSOFT,
            description="Use the shared agent-level Microsoft OAuth configuration.",
        ),
    ]
    OAUTH_SCOPES: Annotated[
        Union[dict[str, str], list[MicrosoftGraphScopes]],
        Field(
            default=[
                MicrosoftGraphScopes.USER_READ,
                MicrosoftGraphScopes.FILES_READ_ALL,
                MicrosoftGraphScopes.SITES_READ_ALL,
                MicrosoftGraphScopes.OFFLINE_ACCESS,
            ],
            description="Microsoft Graph OAuth scopes requested by the agent.",
            validation_alias=AliasChoices(
                "MICROSOFT_GRAPH_OAUTH_SCOPES",
                "MICROSOFT_OAUTH_SCOPES",
                "SHAREPOINT_OAUTH_SCOPES",
            ),
        ),
    ]
    GEMINI_MICROSOFT_AUTH_ID: Annotated[
        Optional[str],
        Field(
            default="mock-ge-microsoft-auth-id",
            description="Shared Auth Resource ID for Microsoft Graph MCP servers.",
            validation_alias=AliasChoices(
                "GEMINI_MICROSOFT_AUTH_ID",
                "MICROSOFT_AUTH_ID",
                "GEMINI_SHAREPOINT_AUTH_ID",
                "SHAREPOINT_AUTH_ID",
            ),
        ),
    ]

    @property
    def auth_resource_id(self) -> Optional[str]:
        """Returns the Microsoft-wide Gemini Enterprise auth resource ID."""
        return self.GEMINI_MICROSOFT_AUTH_ID

    @field_validator("OAUTH_SCOPES", mode="after")
    @classmethod
    def validate_oauth_scopes(
        cls, v: Union[list[MicrosoftGraphScopes], dict[str, str]]
    ) -> dict[str, str]:
        return _scopes_to_dict(v, "microsoft graph access")


# Global MCP configuration instances
BIGQUERY_MCP_CONFIG = BigQueryMCPConfig()
DRIVE_MCP_CONFIG = DriveMCPConfig()
CALENDAR_MCP_CONFIG = CalendarMCPConfig()
GCS_MCP_CONFIG = GCSMCPConfig()
SHAREPOINT_MCP_CONFIG = SharePointMCPConfig()
