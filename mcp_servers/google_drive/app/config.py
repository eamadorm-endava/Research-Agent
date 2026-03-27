from __future__ import annotations

from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
GOOGLE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"
GOOGLE_SLIDE_MIME = "application/vnd.google-apps.presentation"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"
PDF_MIME = "application/pdf"
PLAIN_TEXT_MIME = "text/plain"
CSV_MIME = "text/csv"
OCTET_STREAM_MIME = "application/octet-stream"
FULL_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
FILE_LIST_FIELDS = (
    "files("
    "id,name,mimeType,modifiedTime,webViewLink,size,parents,"
    "owners(displayName,emailAddress),version,createdTime"
    ")"
)
FILE_METADATA_FIELDS = (
    "id,name,mimeType,modifiedTime,webViewLink,size,parents,"
    "owners(displayName,emailAddress),version,createdTime"
)
PATH_RESOLUTION_FIELDS = "id,name,parents"


class DriveMcpConfigBase(BaseSettings):
    """Shared immutable configuration base for the Drive MCP server."""

    model_config = SettingsConfigDict(
        extra="forbid",
        frozen=True,
        env_file_encoding="utf-8",
    )


class DriveApiConfig(DriveMcpConfigBase):
    """Configuration for Google Drive API endpoints, MIME types, and scopes."""

    google_doc: Annotated[
        str, Field(default=GOOGLE_DOC_MIME, description="Google Docs MIME type.")
    ]
    google_sheet: Annotated[
        str, Field(default=GOOGLE_SHEET_MIME, description="Google Sheets MIME type.")
    ]
    google_slide: Annotated[
        str, Field(default=GOOGLE_SLIDE_MIME, description="Google Slides MIME type.")
    ]
    google_folder: Annotated[
        str,
        Field(default=GOOGLE_FOLDER_MIME, description="Google Drive folder MIME type."),
    ]
    pdf: Annotated[str, Field(default=PDF_MIME, description="PDF MIME type.")]
    plain_text: Annotated[
        str, Field(default=PLAIN_TEXT_MIME, description="Plain-text MIME type.")
    ]
    octet_stream: Annotated[
        str, Field(default=OCTET_STREAM_MIME, description="Generic binary MIME type.")
    ]
    export_text_plain: Annotated[
        str, Field(default=PLAIN_TEXT_MIME, description="Plain-text export MIME type.")
    ]
    export_csv: Annotated[
        str, Field(default=CSV_MIME, description="CSV export MIME type.")
    ]
    file_list_fields: Annotated[
        str,
        Field(
            default=FILE_LIST_FIELDS,
            description="Drive API fields selector used when listing/searching files.",
        ),
    ]
    file_metadata_fields: Annotated[
        str,
        Field(
            default=FILE_METADATA_FIELDS,
            description="Drive API fields selector used when reading a single file metadata record.",
        ),
    ]
    path_resolution_fields: Annotated[
        str,
        Field(
            default=PATH_RESOLUTION_FIELDS,
            description="Drive API fields selector used to resolve synthetic folder paths.",
        ),
    ]
    order_by: Annotated[
        str, Field(default="modifiedTime desc", description="Default Drive sort order.")
    ]
    drive_scope: Annotated[
        str,
        Field(
            default=FULL_DRIVE_SCOPE,
            description="Full Drive scope used for file and folder management operations.",
        ),
    ]
    read_scopes: Annotated[
        tuple[str, ...],
        Field(
            default=(FULL_DRIVE_SCOPE,),
            description="Scopes used for Drive read/list/search operations.",
        ),
    ]
    write_doc_scopes: Annotated[
        tuple[str, ...],
        Field(
            default=(FULL_DRIVE_SCOPE,),
            description="Scopes used when creating Google Docs and inserting text.",
        ),
    ]
    write_pdf_scopes: Annotated[
        tuple[str, ...],
        Field(
            default=(FULL_DRIVE_SCOPE,),
            description="Scopes used when uploading generated PDFs.",
        ),
    ]
    management_scopes: Annotated[
        tuple[str, ...],
        Field(
            default=(FULL_DRIVE_SCOPE,),
            description="Scopes used for create/move/rename folder and file management operations.",
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


class DrivePdfConfig(DriveMcpConfigBase):
    """Configuration for PDF generation from text."""

    left_margin: Annotated[
        int, Field(default=72, ge=0, description="Left PDF margin in points.")
    ]
    right_margin: Annotated[
        int, Field(default=72, ge=0, description="Right PDF margin in points.")
    ]
    top_margin: Annotated[
        int, Field(default=72, ge=0, description="Top PDF margin in points.")
    ]
    bottom_margin: Annotated[
        int, Field(default=72, ge=0, description="Bottom PDF margin in points.")
    ]
    font_name: Annotated[
        str, Field(default="Helvetica", description="Font used when generating PDFs.")
    ]
    font_size: Annotated[
        int,
        Field(
            default=11, ge=6, le=24, description="Body font size for generated PDFs."
        ),
    ]
    leading: Annotated[
        int,
        Field(default=14, ge=8, le=40, description="Line spacing in generated PDFs."),
    ]
    paragraph_spacing: Annotated[
        int,
        Field(
            default=8,
            ge=0,
            le=40,
            description="Space after each paragraph in generated PDFs.",
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
DRIVE_PDF_CONFIG = DrivePdfConfig()
DRIVE_SERVER_CONFIG = DriveServerConfig()
