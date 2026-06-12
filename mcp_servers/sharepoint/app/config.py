from enum import StrEnum
from typing import Annotated

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MicrosoftGraphScope(StrEnum):
    """Microsoft Graph delegated scopes required by read-only Microsoft MCP servers."""

    USER_READ = "User.Read"
    FILES_READ_ALL = "Files.Read.All"
    SITES_READ_ALL = "Sites.Read.All"


class SharePointMcpConfigBase(BaseSettings):
    """Shared immutable configuration base for the SharePoint MCP server."""

    model_config = SettingsConfigDict(
        extra="forbid",
        frozen=True,
        env_file_encoding="utf-8",
    )


class SharePointApiConfig(SharePointMcpConfigBase):
    """Configuration for Microsoft Graph endpoints and delegated scopes."""

    graph_base_url: Annotated[
        str,
        Field(
            default="https://graph.microsoft.com/v1.0",
            description="Microsoft Graph v1.0 API base URL.",
        ),
    ]
    required_scopes: Annotated[
        tuple[MicrosoftGraphScope, ...],
        Field(
            default=(
                MicrosoftGraphScope.USER_READ,
                MicrosoftGraphScope.FILES_READ_ALL,
                MicrosoftGraphScope.SITES_READ_ALL,
            ),
            description="Delegated Microsoft Graph scopes required by this read-only server.",
        ),
    ]
    page_size: Annotated[
        int,
        Field(
            default=25,
            ge=1,
            le=999,
            description="Default Microsoft Graph page size for list operations.",
        ),
    ]
    max_pages: Annotated[
        int,
        Field(
            default=10,
            ge=1,
            le=100,
            description="Maximum number of Microsoft Graph pages to follow per request.",
        ),
    ]
    request_timeout_seconds: Annotated[
        float,
        Field(
            default=30.0,
            ge=1.0,
            le=300.0,
            description="HTTP timeout in seconds for Microsoft Graph requests.",
        ),
    ]


class MicrosoftAuthConfig(SharePointMcpConfigBase):
    """Shared configuration for Microsoft Entra token validation."""

    tenant_id: Annotated[
        str,
        Field(
            default="organizations",
            validation_alias=AliasChoices(
                "MICROSOFT_TENANT_ID", "SHAREPOINT_TENANT_ID"
            ),
            description="Microsoft Entra tenant ID or tenant alias used in issuer metadata.",
        ),
    ]
    issuer_url_template: Annotated[
        str,
        Field(
            default="https://login.microsoftonline.com/{tenant_id}/v2.0",
            description="Microsoft Entra issuer URL template.",
        ),
    ]

    @property
    def issuer_url(self) -> str:
        """Returns the configured Microsoft Entra issuer URL."""
        return self.issuer_url_template.format(tenant_id=self.tenant_id)


class SharePointLandingZoneConfig(SharePointMcpConfigBase):
    """Configuration for secure file-copy ingestion into the ADK landing zone."""

    bucket_name: Annotated[
        str,
        Field(
            default="mock-project-id-ai-agent-landing-zone",
            validation_alias=AliasChoices(
                "SHAREPOINT_LANDING_ZONE_BUCKET",
                "LANDING_ZONE_BUCKET",
                "GCS_LANDING_ZONE_BUCKET",
            ),
            description="Central GCS Landing Zone bucket used for file injection.",
        ),
    ]
    data_source_prefix: Annotated[
        str,
        Field(
            default="sharepoint",
            min_length=1,
            max_length=50,
            description="Prefix used in landing-zone object names for SharePoint files.",
        ),
    ]
    upload_chunk_size_bytes: Annotated[
        int,
        Field(
            default=1024 * 1024,
            ge=64 * 1024,
            le=16 * 1024 * 1024,
            description="Streaming chunk size used when copying SharePoint files to GCS.",
        ),
    ]


class SharePointServerConfig(SharePointMcpConfigBase):
    """Configuration for the MCP server network and runtime behavior."""

    server_name: Annotated[
        str,
        Field(
            default="sharepoint-mcp-server",
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
            default=8080,
            ge=1,
            le=65535,
            description="Default port for the SharePoint MCP server.",
        ),
    ]
    default_log_level: Annotated[
        str,
        Field(
            default="INFO",
            description="Default local logging level.",
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


SHAREPOINT_API_CONFIG = SharePointApiConfig()
MICROSOFT_AUTH_CONFIG = MicrosoftAuthConfig()
SHAREPOINT_LANDING_ZONE_CONFIG = SharePointLandingZoneConfig()
SHAREPOINT_SERVER_CONFIG = SharePointServerConfig()
