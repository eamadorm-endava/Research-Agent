from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from enum import StrEnum
from typing import Annotated, Union


class DriveScopes(StrEnum):
    """
    Enum for Google Drive OAuth scopes.
    """

    DRIVE = "https://www.googleapis.com/auth/drive"


class BigQueryScopes(StrEnum):
    """
    Enum for Google BigQuery OAuth scopes.
    """

    BIGQUERY = "https://www.googleapis.com/auth/bigquery"


class CalendarScopes(StrEnum):
    """
    Enum for Google Calendar OAuth scopes.
    """

    CALENDAR_READONLY = "https://www.googleapis.com/auth/calendar.events.readonly"
    MEET_READONLY = "https://www.googleapis.com/auth/meetings.space.readonly"


class BaseMCPConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
    )
    """
    Generic MCP server configuration that child classes inherit from.
    """

    GENERAL_TIMEOUT: Annotated[
        int,
        Field(
            default=60,
            description="Timeout in seconds for MCP servers.",
        ),
    ]


class BigQueryMCPConfig(BaseMCPConfig):
    URL: Annotated[
        str,
        Field(
            default="http://localhost:8080",
            description="BigQuery MCP Server URL",
            validation_alias="BIGQUERY_URL",  # validation_alias is used to map the environment variable to the field
        ),
    ]
    ENDPOINT: Annotated[
        str,
        Field(
            default="/mcp",
            description="BigQuery MCP Server Endpoint",
            validation_alias="BIGQUERY_ENDPOINT",  # validation_alias is used to map the environment variable to the field
        ),
    ]
    OAUTH_SCOPES: Annotated[
        Union[dict[str, str], list[BigQueryScopes]],
        Field(
            default=[BigQueryScopes.BIGQUERY],
            description="OAuth scopes requested by the agent.",
            validation_alias="BIGQUERY_OAUTH_SCOPES",  # validation_alias is used to map the environment variable to the field
        ),
    ]

    @field_validator("OAUTH_SCOPES", mode="after")
    @classmethod
    def validate_oauth_scopes(
        cls, v: Union[list[BigQueryScopes], dict[str, str]]
    ) -> dict[str, str]:
        if isinstance(v, dict):
            return v
        return {scope.value: "google bigquery access" for scope in v}


class DriveMCPConfig(BaseMCPConfig):
    URL: Annotated[
        str,
        Field(
            default="http://localhost:8081",
            description="Google Drive MCP Server URL",
            validation_alias="DRIVE_URL",  # validation_alias is used to map the environment variable to the field
        ),
    ]
    ENDPOINT: Annotated[
        str,
        Field(
            default="/mcp",
            description="Google Drive MCP Server Endpoint",
            validation_alias="DRIVE_ENDPOINT",  # validation_alias is used to map the environment variable to the field
        ),
    ]
    OAUTH_SCOPES: Annotated[
        Union[dict[str, str], list[DriveScopes]],
        Field(
            default=[DriveScopes.DRIVE],
            description="OAuth scopes requested by the agent.",
            validation_alias="DRIVE_OAUTH_SCOPES",  # validation_alias is used to map the environment variable to the field
        ),
    ]

    @field_validator("OAUTH_SCOPES", mode="after")
    @classmethod
    def validate_oauth_scopes(
        cls, v: Union[list[DriveScopes], dict[str, str]]
    ) -> dict[str, str]:
        if isinstance(v, dict):
            return v
        return {scope.value: "google drive access" for scope in v}


class CalendarMCPConfig(BaseMCPConfig):
    URL: Annotated[
        str,
        Field(
            default="http://localhost:8083",
            description="Google Calendar MCP Server URL",
            validation_alias="CALENDAR_URL",  # validation_alias is used to map the environment variable to the field
        ),
    ]
    ENDPOINT: Annotated[
        str,
        Field(
            default="/mcp",
            description="Google Calendar MCP Server Endpoint",
            validation_alias="CALENDAR_ENDPOINT",  # validation_alias is used to map the environment variable to the field
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
            validation_alias="CALENDAR_OAUTH_SCOPES",  # validation_alias is used to map the environment variable to the field
        ),
    ]

    @field_validator("OAUTH_SCOPES", mode="after")
    @classmethod
    def validate_oauth_scopes(
        cls, v: Union[list[CalendarScopes], dict[str, str]]
    ) -> dict[str, str]:
        if isinstance(v, dict):
            return v
        return {scope.value: "google calendar access" for scope in v}


class GCSMCPConfig(BaseMCPConfig):
    URL: Annotated[
        str,
        Field(
            default="http://localhost:8082",
            description="GCS MCP Server URL",
            validation_alias="GCS_URL",  # validation_alias is used to map the environment variable to the field
        ),
    ]
    ENDPOINT: Annotated[
        str,
        Field(
            default="/mcp",
            description="GCS MCP Server Endpoint",
            validation_alias="GCS_ENDPOINT",  # validation_alias is used to map the environment variable to the field
        ),
    ]
    # GCS relies purely on Google SDK application default credentials downstream, so it does not expose standard scopes mapping.
