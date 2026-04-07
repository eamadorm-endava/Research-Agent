from __future__ import annotations

from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BigQueryMcpConfigBase(BaseSettings):
    """Shared immutable configuration base for the BigQuery MCP server."""

    model_config = SettingsConfigDict(
        extra="forbid",
        frozen=True,
        env_file_encoding="utf-8",
    )


class BigQueryApiConfig(BigQueryMcpConfigBase):
    """Configuration for BigQuery API interaction settings."""

    read_write_scopes: Annotated[
        tuple[str, ...],
        Field(
            default=("https://www.googleapis.com/auth/bigquery",),
            description="Scopes used for delegated user BigQuery operations.",
        ),
    ]


class BigQueryAuthConfig(BigQueryMcpConfigBase):
    """Configuration for Google OAuth authentication endpoints and client details."""

    google_token_info_url: Annotated[
        str,
        Field(
            default="https://oauth2.googleapis.com/tokeninfo",
            description="Google OAuth2 token info endpoint for access token validation.",
        ),
    ]
    google_accounts_issuer_url: Annotated[
        str,
        Field(
            default="https://accounts.google.com",
            description="Google Accounts issuer URL.",
        ),
    ]


class BigQueryServerConfig(BigQueryMcpConfigBase):
    """Configuration for the MCP server network/runtime settings."""

    server_name: Annotated[
        str,
        Field(
            default="bigquery-mcp-server",
            description="Published name of the BigQuery MCP server.",
        ),
    ]
    default_host: Annotated[
        str,
        Field(
            default="0.0.0.0",
            description="Default interface the BigQuery MCP server binds to.",
        ),
    ]
    default_port: Annotated[
        int,
        Field(
            default=8080,
            ge=1,
            le=65535,
            description="Default port for the BigQuery MCP server.",
        ),
    ]
    default_log_level: Annotated[
        str,
        Field(
            default="INFO",
            description="Default log level for the local BigQuery MCP server.",
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


BIGQUERY_API_CONFIG = BigQueryApiConfig()
BIGQUERY_AUTH_CONFIG = BigQueryAuthConfig()
BIGQUERY_SERVER_CONFIG = BigQueryServerConfig()
