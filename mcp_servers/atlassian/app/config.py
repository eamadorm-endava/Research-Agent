from typing import Annotated, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AtlassianMcpConfigBase(BaseSettings):
    """Shared immutable configuration base for the Atlassian MCP server."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )


class AtlassianAPIConfig(AtlassianMcpConfigBase):
    """Configuration for delegated Atlassian OAuth routing."""

    jira_cloud_id: Annotated[
        Optional[str],
        Field(
            default="",
            description="Optional Atlassian Cloud ID override for multi-site tenants.",
            validation_alias="JIRA_CLOUD_ID",
        ),
    ]


class AtlassianServerConfig(AtlassianMcpConfigBase):
    """Configuration for the MCP server network and runtime settings."""

    server_name: Annotated[
        str,
        Field(
            default="atlassian-mcp-server",
            description="Name of the Atlassian MCP server.",
        ),
    ]
    default_host: Annotated[
        str,
        Field(
            default="0.0.0.0",
            description="Interface to bind to.",
        ),
    ]
    default_port: Annotated[
        int,
        Field(
            default=8085,
            ge=1,
            le=65535,
            description="Default port.",
        ),
    ]
    default_log_level: Annotated[
        str,
        Field(
            default="INFO",
            description="Default log level.",
        ),
    ]
    stateless_http: Annotated[
        bool,
        Field(
            default=True,
            description="Run in stateless HTTP mode.",
        ),
    ]
    landing_zone_bucket: Annotated[
        str,
        Field(
            default="",
            description="Landing Zone bucket name for file uploads.",
            validation_alias="LANDING_ZONE_BUCKET",
        ),
    ]


ATLASSIAN_API_CONFIG = AtlassianAPIConfig()
ATLASSIAN_SERVER_CONFIG = AtlassianServerConfig()
