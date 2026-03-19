from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class DriveMcpConfigBase(BaseModel):
    """Shared immutable configuration base for the Drive MCP server."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DriveApiConfig(DriveMcpConfigBase):
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

    def read_scopes_list(self) -> list[str]:
        return list(self.read_scopes)

    def write_doc_scopes_list(self) -> list[str]:
        return list(self.write_doc_scopes)

    def write_pdf_scopes_list(self) -> list[str]:
        return list(self.write_pdf_scopes)


class DriveAuthConfig(DriveMcpConfigBase):
    delegated_token_header_env: Annotated[
        str,
        Field(
            default="DRIVE_DELEGATED_TOKEN_HEADER",
            description="Environment variable that can override the delegated Drive token header name.",
        ),
    ]
    delegated_token_header_default: Annotated[
        str,
        Field(
            default="x-drive-access-token",
            description="Default header name used to forward the delegated Drive user access token.",
        ),
    ]
    use_adc_env_names: Annotated[
        tuple[str, ...],
        Field(
            default=("DRIVE_USE_ADC", "USE_ADC_FOR_DRIVE"),
            description="Environment variables that enable ADC-based credentials for the Drive MCP server.",
        ),
    ]
    allow_local_oauth_env_names: Annotated[
        tuple[str, ...],
        Field(
            default=("DRIVE_ALLOW_LOCAL_OAUTH", "ALLOW_LOCAL_OAUTH"),
            description="Environment variables that enable local OAuth for the Drive MCP server.",
        ),
    ]
    oauth_client_secret_env_names: Annotated[
        tuple[str, ...],
        Field(
            default=(
                "DRIVE_GOOGLE_OAUTH_CLIENT_SECRETS",
                "GOOGLE_OAUTH_CLIENT_SECRETS",
            ),
            description="Environment variables checked for the local OAuth client-secret path.",
        ),
    ]
    token_cache_env: Annotated[
        str,
        Field(
            default="DRIVE_TOKEN_CACHE",
            description="Environment variable that overrides the local OAuth token cache path.",
        ),
    ]
    default_client_secret_path: Annotated[
        str,
        Field(
            default="client_secret.json",
            description="Default local OAuth client-secret path.",
        ),
    ]
    default_token_cache_path: Annotated[
        str,
        Field(
            default=".cache/drive_token.json",
            description="Default Drive token cache path.",
        ),
    ]
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


class DriveServerConfig(DriveMcpConfigBase):
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
    route_path: Annotated[
        str,
        Field(default="/mcp", description="Mounted MCP route path."),
    ]
    header_context_key: Annotated[
        str,
        Field(
            default="drive_mcp_headers",
            description="Context variable key used to cache inbound HTTP headers.",
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
