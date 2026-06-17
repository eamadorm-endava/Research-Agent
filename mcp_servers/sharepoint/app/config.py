from __future__ import annotations

from typing import Annotated

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SharePointMCPConfigBase(BaseSettings):
    """Shared immutable configuration base for the SharePoint MCP server."""

    model_config = SettingsConfigDict(
        extra="ignore",
        frozen=True,
        env_file=".env",
        env_file_encoding="utf-8",
    )


class SharePointAuthConfig(SharePointMCPConfigBase):
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
            ],
            description="The OAuth scopes required for SharePoint content access.",
        ),
    ]


class SharePointServerConfig(SharePointMCPConfigBase):
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
            default="osiris-sharepoint-mcp-server",
            description="Published name of the SharePoint MCP server.",
        ),
    ]
    default_host: Annotated[
        str,
        Field(
            default="0.0.0.0",
            description="Default interface the SharePoint MCP server binds to.",
        ),
    ]
    default_port: Annotated[
        int,
        Field(
            default=8086,
            ge=1,
            le=65535,
            description="Default port for the local SharePoint MCP server.",
        ),
    ]
    default_log_level: Annotated[
        str,
        Field(
            default="info",
            description="Default log level for the local SharePoint MCP server.",
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
    max_items_per_page: Annotated[
        int,
        Field(
            default=20,
            ge=1,
            le=100,
            description="Maximum number of objects returned per page.",
        ),
    ]
    max_list_item_preview_fields: Annotated[
        int,
        Field(
            default=8,
            ge=1,
            le=30,
            description="Maximum field values used to build SharePoint list-item previews.",
        ),
    ]
    max_page_text_chars: Annotated[
        int,
        Field(
            default=8000,
            ge=500,
            description="Maximum extracted text characters returned from one SharePoint page.",
        ),
    ]
    cache_ttl_seconds: Annotated[
        int,
        Field(
            default=600,
            ge=1,
            description="Time-to-live for cached Graph API collection responses in seconds.",
        ),
    ]


SHAREPOINT_AUTH_CONFIG = SharePointAuthConfig()
SHAREPOINT_SERVER_CONFIG = SharePointServerConfig()
