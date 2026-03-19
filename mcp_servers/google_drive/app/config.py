from __future__ import annotations

from typing import Annotated, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DriveMcpConfigBase(BaseSettings):
    """Shared immutable configuration base for the Drive MCP server."""

    model_config = SettingsConfigDict(
        extra="forbid",
        frozen=True,
        env_file_encoding="utf-8",
        # Allow case-insensitive environment variable matching if needed
        # case_sensitive=False,
    )


class DriveApiConfig(DriveMcpConfigBase):
    """Configuration for Google Drive API endpoints and MIME types."""

    google_doc: Annotated[
        str,
        Field(
            default="application/vnd.google-apps.document",
            description="Google Docs MIME type.",
        ),
    ]
    google_sheet: Annotated[
        str,
        Field(
            default="application/vnd.google-apps.spreadsheet",
            description="Google Sheets MIME type.",
        ),
    ]
    google_slide: Annotated[
        str,
        Field(
            default="application/vnd.google-apps.presentation",
            description="Google Slides MIME type.",
        ),
    ]
    google_folder: Annotated[
        str,
        Field(
            default="application/vnd.google-apps.folder",
            description="Google Drive folder MIME type.",
        ),
    ]
    pdf: Annotated[
        str,
        Field(default="application/pdf", description="PDF MIME type."),
    ]
    export_text_plain: Annotated[
        str,
        Field(default="text/plain", description="Plain-text export MIME type."),
    ]
    export_csv: Annotated[
        str,
        Field(default="text/csv", description="CSV export MIME type."),
    ]
    file_list_fields: Annotated[
        str,
        Field(
            default="files(id,name,mimeType,modifiedTime,webViewLink)",
            description="Drive API fields selector used when listing/searching files.",
        ),
    ]
    file_metadata_fields: Annotated[
        str,
        Field(
            default="id,name,mimeType,modifiedTime,webViewLink",
            description="Drive API fields selector used when reading a single file metadata record.",
        ),
    ]
    order_by: Annotated[
        str,
        Field(default="modifiedTime desc", description="Default Drive sort order."),
    ]
    read_scopes: Annotated[
        tuple[str, ...],
        Field(
            default=("https://www.googleapis.com/auth/drive.readonly",),
            description="Scopes used for Drive read/list/search operations.",
        ),
    ]
    write_doc_scopes: Annotated[
        tuple[str, ...],
        Field(
            default=(
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/documents",
            ),
            description="Scopes used when creating Google Docs and inserting text.",
        ),
    ]
    write_pdf_scopes: Annotated[
        tuple[str, ...],
        Field(
            default=("https://www.googleapis.com/auth/drive.file",),
            description="Scopes used when uploading generated PDFs.",
        ),
    ]


class DriveAuthConfig(DriveMcpConfigBase):
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
    google_oauth2_auth_url: Annotated[
        str,
        Field(
            default="https://accounts.google.com/o/oauth2/v2/auth",
            description="Google OAuth2 authorization endpoint.",
        ),
    ]
    google_oauth_client_id: Annotated[
        Optional[str],
        Field(
            default=None,
            validation_alias="DRIVE_OAUTH_CLIENT_ID",
            description="Google OAuth2 Client ID for authentication.",
        ),
    ]
    google_oauth_redirect_uri: Annotated[
        Optional[str],
        Field(
            default=None,
            validation_alias="DRIVE_OAUTH_REDIRECT_URI",
            description="Google OAuth2 Redirect URI.",
        ),
    ]


class DriveServerConfig(DriveMcpConfigBase):
    """Configuration for the MCP server's network and operational settings."""

    server_name: Annotated[
        str,
        Field(
            default="google-drive-mcp-server",
            description="Published name of the Drive MCP server.",
        ),
    ]
    default_host: Annotated[
        str,
        Field(
            default="0.0.0.0",
            description="Default interface the Drive MCP server binds to.",
        ),
    ]
    default_port: Annotated[
        int,
        Field(
            default=8080,
            ge=1,
            le=65535,
            description="Default port for the Drive MCP server.",
        ),
    ]
    default_log_level: Annotated[
        str,
        Field(
            default="info",
            description="Default log level for the local Drive MCP server.",
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


DRIVE_API_CONFIG = DriveApiConfig()
DRIVE_AUTH_CONFIG = DriveAuthConfig()
DRIVE_SERVER_CONFIG = DriveServerConfig()
