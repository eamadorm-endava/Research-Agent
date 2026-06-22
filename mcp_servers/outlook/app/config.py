from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OutlookMCPConfigBase(BaseSettings):
    """Shared immutable configuration base for the Outlook MCP server."""

    model_config = SettingsConfigDict(
        extra="ignore",
        frozen=True,
        env_file=".env",
        env_file_encoding="utf-8",
    )


class OutlookAuthConfig(OutlookMCPConfigBase):
    """Configuration for Microsoft Entra authentication settings."""

    TENANT_ID: Annotated[
        str,
        Field(
            default="",
            validation_alias=AliasChoices("MICROSOFT_TENANT_ID", "TENANT_ID"),
            description="The Microsoft Entra Tenant ID.",
        ),
    ]
    CLIENT_ID: Annotated[
        str,
        Field(
            default="",
            validation_alias=AliasChoices("MICROSOFT_CLIENT_ID", "CLIENT_ID"),
            description="The Microsoft Entra App Registration Client ID.",
        ),
    ]
    CLIENT_SECRET: Annotated[
        str,
        Field(
            default="",
            validation_alias=AliasChoices("MICROSOFT_CLIENT_SECRET", "CLIENT_SECRET"),
            description="The Microsoft Entra App Registration Client Secret.",
        ),
    ]
    SCOPES: Annotated[
        list[str],
        Field(
            default=[
                "offline_access",
                "Files.Read.All",
                "Sites.Read.All",
                "User.Read.All", 
                "Mail.Read", 
                "Mail.Read.Shared",
            ],
            description="The OAuth scopes required for OneDrive and SharePoint access.",
        ),
    ]


class OutlookServerConfig(OutlookMCPConfigBase):
    """Configuration for the MCP server network/runtime settings."""

    graph_api_base_url: Annotated[
        str,
        Field(
            default="https://graph.microsoft.com/v1.0",
            description="The base URL for the Microsoft Graph API.",
        ),
    ]

    server_name: Annotated[
        str,
        Field(
            default="osiris-outlook-mcp-server",
            description="Published name of the Outlook MCP server.",
        ),
    ]
    default_host: Annotated[
        str,
        Field(
            default="0.0.0.0",
            description="Default interface the Outlook MCP server binds to.",
        ),
    ]
    default_port: Annotated[
        int,
        Field(
            default=8086,
            ge=1,
            le=65535,
            description="Default port for the Outlook MCP server.",
        ),
    ]
    default_log_level: Annotated[
        str,
        Field(
            default="info",
            description="Default log level for the local Outlook MCP server.",
        ),
    ]
    stateless_http: Annotated[
        bool,
        Field(
            default=True,
            description="Whether the server should use stateless HTTP mode.",
        ),
    ]
    landing_zone_bucket: Annotated[
        str,
        Field(
            default="mock-landing-zone-bucket",
            validation_alias=AliasChoices(
                "GCS_LANDING_ZONE_BUCKET", "LANDING_ZONE_BUCKET"
            ),
            description="The GCS bucket acting as the AI Agent landing zone.",
        ),
    ]
    timeout_seconds: Annotated[
        int, 
        Field(
            default=30,
            description="HTTP timeout in seconds"
        )
    ]
    max_page_size: Annotated[
        int, 
        Field(
            default=25,
            description="Maximum number of messages per request"
        )
    ]


OUTLOOK_AUTH_CONFIG = OutlookAuthConfig()
OUTLOOK_SERVER_CONFIG = OutlookServerConfig()