from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class DriveToolConfigBase(BaseModel):
    """Shared immutable configuration base for the in-process Drive tool package."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DriveToolRuntimeConfig(DriveToolConfigBase):
    state_last_results_key: Annotated[
        str,
        Field(
            default="drive_last_results",
            description="ToolContext state key used to store the latest Drive list/search results.",
        ),
    ]
    default_max_results: Annotated[
        int,
        Field(
            default=10,
            ge=1,
            description="Default maximum number of Drive files returned by list/search helpers.",
        ),
    ]
    default_max_text_chars: Annotated[
        int,
        Field(
            default=60000,
            ge=1,
            description="Default maximum number of extracted text characters returned to the agent.",
        ),
    ]


class DriveMimeTypeConfig(DriveToolConfigBase):
    google_doc: Annotated[
        str,
        Field(default="application/vnd.google-apps.document", description="Google Docs MIME type."),
    ]
    google_sheet: Annotated[
        str,
        Field(default="application/vnd.google-apps.spreadsheet", description="Google Sheets MIME type."),
    ]
    google_slide: Annotated[
        str,
        Field(default="application/vnd.google-apps.presentation", description="Google Slides MIME type."),
    ]
    google_folder: Annotated[
        str,
        Field(default="application/vnd.google-apps.folder", description="Google Drive folder MIME type."),
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


class DriveScopeConfig(DriveToolConfigBase):
    read_only: Annotated[
        tuple[str, ...],
        Field(
            default=("https://www.googleapis.com/auth/drive.readonly",),
            description="Scopes used for read-only Drive list/search/content retrieval operations.",
        ),
    ]
    write_document: Annotated[
        tuple[str, ...],
        Field(
            default=(
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/documents",
            ),
            description="Scopes used when creating and writing Google Docs.",
        ),
    ]
    write_pdf: Annotated[
        tuple[str, ...],
        Field(
            default=("https://www.googleapis.com/auth/drive.file",),
            description="Scopes used when uploading generated PDFs.",
        ),
    ]

    def read_only_list(self) -> list[str]:
        return list(self.read_only)

    def write_document_list(self) -> list[str]:
        return list(self.write_document)

    def write_pdf_list(self) -> list[str]:
        return list(self.write_pdf)


class DriveAuthEnvConfig(DriveToolConfigBase):
    gemini_enterprise_auth_id_env: Annotated[
        str,
        Field(
            default="GEMINI_ENTERPRISE_AUTH_ID",
            description="Environment variable holding the Gemini Enterprise authorization ID.",
        ),
    ]
    use_adc_env: Annotated[
        str,
        Field(
            default="USE_ADC_FOR_DRIVE",
            description="Environment variable that enables ADC-based Drive auth for local/server use.",
        ),
    ]
    allow_local_oauth_env: Annotated[
        str,
        Field(
            default="ALLOW_LOCAL_OAUTH",
            description="Environment variable that enables local OAuth for Drive tooling.",
        ),
    ]
    oauth_client_secrets_env: Annotated[
        str,
        Field(
            default="GOOGLE_OAUTH_CLIENT_SECRETS",
            description="Environment variable pointing to the local OAuth client-secret JSON file.",
        ),
    ]
    token_cache_env: Annotated[
        str,
        Field(
            default="DRIVE_TOKEN_CACHE",
            description="Environment variable pointing to the cached Drive OAuth token path.",
        ),
    ]
    default_client_secrets_path: Annotated[
        str,
        Field(default="client_secret.json", description="Default path to the local OAuth client-secret file."),
    ]
    default_token_cache_path: Annotated[
        str,
        Field(default=".cache/drive_token.json", description="Default path to the cached Drive OAuth token."),
    ]
    injected_token_candidate_keys: Annotated[
        tuple[str, ...],
        Field(
            default=("access_token", "token", "value"),
            description="Accepted keys when the injected auth token is stored as a mapping.",
        ),
    ]


DRIVE_TOOL_RUNTIME_CONFIG = DriveToolRuntimeConfig()
DRIVE_MIME_TYPE_CONFIG = DriveMimeTypeConfig()
DRIVE_SCOPE_CONFIG = DriveScopeConfig()
DRIVE_AUTH_ENV_CONFIG = DriveAuthEnvConfig()
