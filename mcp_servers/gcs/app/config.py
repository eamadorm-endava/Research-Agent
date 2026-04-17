from __future__ import annotations

from typing import Annotated

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GcsMcpConfigBase(BaseSettings):
    """Shared immutable configuration base for the GCS MCP server."""

    model_config = SettingsConfigDict(
        extra="ignore",
        frozen=True,
        env_file=".env",
        env_file_encoding="utf-8",
    )


class GcsApiConfig(GcsMcpConfigBase):
    """Configuration for GCS API interaction settings."""

    cloud_platform_scope: Annotated[
        str,
        Field(
            default="https://www.googleapis.com/auth/cloud-platform",
            description=(
                "Broad Google Cloud scope that can satisfy delegated Cloud Storage "
                "operations when issued by Gemini Enterprise or local OAuth."
            ),
        ),
    ]
    storage_read_only_scope: Annotated[
        str,
        Field(
            default="https://www.googleapis.com/auth/devstorage.read_only",
            description="Read-only Cloud Storage scope.",
        ),
    ]
    storage_read_write_scope: Annotated[
        str,
        Field(
            default="https://www.googleapis.com/auth/devstorage.read_write",
            description="Read-write Cloud Storage scope.",
        ),
    ]
    storage_full_control_scope: Annotated[
        str,
        Field(
            default="https://www.googleapis.com/auth/devstorage.full_control",
            description="Full-control Cloud Storage scope.",
        ),
    ]

    read_write_scopes: Annotated[
        tuple[str, ...],
        Field(
            default=("https://www.googleapis.com/auth/devstorage.read_write",),
            description="Scopes used for delegated user GCS operations.",
        ),
    ]


class GcsAuthConfig(GcsMcpConfigBase):
    """Configuration for Google OAuth authentication endpoints and client details."""

    google_token_info_url_v3: Annotated[
        str,
        Field(
            default="https://www.googleapis.com/oauth2/v3/tokeninfo",
            description="Google OAuth2 v3 token info endpoint for validation.",
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


class GcsServerConfig(GcsMcpConfigBase):
    """Configuration for the MCP server network/runtime settings."""

    server_name: Annotated[
        str,
        Field(
            default="gcs-mcp-server",
            description="Published name of the GCS MCP server.",
        ),
    ]
    default_host: Annotated[
        str,
        Field(
            default="0.0.0.0",
            description="Default interface the GCS MCP server binds to.",
        ),
    ]
    default_port: Annotated[
        int,
        Field(
            default=8080,
            ge=1,
            le=65535,
            description="Default port for the GCS MCP server.",
        ),
    ]
    default_project_id: Annotated[
        str | None,
        Field(
            default=None,
            validation_alias=AliasChoices(
                "GCS_PROJECT_ID",
                "PROJECT_ID",
                "GOOGLE_CLOUD_PROJECT",
            ),
            description=(
                "Default GCP project ID for project-scoped Cloud Storage operations. "
                "Used when the request does not provide project_id."
            ),
        ),
    ]
    default_log_level: Annotated[
        str,
        Field(
            default="info",
            description="Default log level for the local GCS MCP server.",
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


GCS_API_CONFIG = GcsApiConfig()
GCS_AUTH_CONFIG = GcsAuthConfig()
GCS_SERVER_CONFIG = GcsServerConfig()
