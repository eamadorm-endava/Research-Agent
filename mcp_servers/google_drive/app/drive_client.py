from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any, Sequence

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from pypdf import PdfReader

from .config import DRIVE_API_CONFIG, DRIVE_AUTH_CONFIG
from .schemas import AuthenticationError
from .schemas import DriveDocumentModel as DriveTextDocument
from .schemas import DriveFileModel as DriveFile


class DriveManager:
    """Manager for Google Drive operations."""

    def __init__(self, creds: Any):
        self.creds = creds
        self.drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    def list_files(
        self,
        *,
        max_results: int = 10,
        folder_id: str | None = None,
        include_folders: bool = False,
    ) -> list[DriveFile]:
        query_parts: list[str] = []
        if folder_id:
            query_parts.append(f"'{_escape_q(folder_id)}' in parents")
        if not include_folders:
            query_parts.append(f"mimeType != '{DRIVE_API_CONFIG.google_folder}'")
        query = " and ".join(query_parts) if query_parts else None

        response = (
            self.drive.files()
            .list(
                q=query,
                pageSize=max_results,
                fields=DRIVE_API_CONFIG.file_list_fields,
                orderBy=DRIVE_API_CONFIG.order_by,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        return [
            DriveFile.model_validate(file_payload)
            for file_payload in response.get("files", [])
        ]

    def search_files(
        self,
        *,
        search_text: str | None = None,
        drive_query: str | None = None,
        max_results: int = 10,
        folder_id: str | None = None,
        include_folders: bool = False,
        mime_types: Sequence[str] | None = None,
    ) -> list[DriveFile]:
        query_parts: list[str] = []

        if drive_query:
            query_parts.append(drive_query)
        else:
            normalized_search_text = (search_text or "").strip()
            if normalized_search_text:
                escaped_search_text = _escape_q(normalized_search_text)
                query_parts.append(
                    f"(name contains '{escaped_search_text}' or fullText contains '{escaped_search_text}')"
                )

        if folder_id:
            query_parts.append(f"'{_escape_q(folder_id)}' in parents")

        if mime_types:
            mime_filters = " or ".join(
                [f"mimeType = '{_escape_q(mime_type)}'" for mime_type in mime_types]
            )
            query_parts.append(f"({mime_filters})")

        if not include_folders:
            query_parts.append(f"mimeType != '{DRIVE_API_CONFIG.google_folder}'")

        query = " and ".join([part for part in query_parts if part]) or None

        response = (
            self.drive.files()
            .list(
                q=query,
                pageSize=max_results,
                fields=DRIVE_API_CONFIG.file_list_fields,
                orderBy=DRIVE_API_CONFIG.order_by,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        return [
            DriveFile.model_validate(file_payload)
            for file_payload in response.get("files", [])
        ]

    def get_file_text(self, file_id: str) -> DriveTextDocument:
        metadata = (
            self.drive.files()
            .get(
                fileId=file_id,
                fields=DRIVE_API_CONFIG.file_metadata_fields,
                supportsAllDrives=True,
            )
            .execute()
        )

        mime_type = metadata.get("mimeType", "")
        file_name = metadata.get("name", "")
        extracted_text = ""

        if mime_type == DRIVE_API_CONFIG.google_doc:
            extracted_text = self._export_bytes(
                file_id, DRIVE_API_CONFIG.export_text_plain
            ).decode("utf-8", errors="ignore")
        elif mime_type == DRIVE_API_CONFIG.google_sheet:
            extracted_text = self._export_bytes(
                file_id, DRIVE_API_CONFIG.export_csv
            ).decode("utf-8", errors="ignore")
        elif mime_type == DRIVE_API_CONFIG.google_slide:
            try:
                extracted_text = self._export_bytes(
                    file_id, DRIVE_API_CONFIG.export_text_plain
                ).decode("utf-8", errors="ignore")
            except Exception:
                pdf_bytes = self._export_bytes(file_id, DRIVE_API_CONFIG.pdf)
                extracted_text = _extract_text_from_pdf_bytes(pdf_bytes)
        else:
            raw_bytes = self._download_bytes(file_id)
            if mime_type == DRIVE_API_CONFIG.pdf or file_name.lower().endswith(".pdf"):
                extracted_text = _extract_text_from_pdf_bytes(raw_bytes)
            else:
                extracted_text = raw_bytes.decode("utf-8", errors="ignore")

        return DriveTextDocument.model_validate(
            {
                **metadata,
                "mimeType": mime_type,
                "name": file_name,
                "text": extracted_text,
            }
        )

    def create_google_doc_from_text(
        self,
        *,
        title: str,
        content: str,
        folder_id: str | None = None,
    ) -> DriveFile:
        file_metadata: dict[str, Any] = {
            "name": title,
            "mimeType": DRIVE_API_CONFIG.google_doc,
        }
        if folder_id:
            file_metadata["parents"] = [folder_id]

        created = (
            self.drive.files()
            .create(
                body=file_metadata,
                fields=DRIVE_API_CONFIG.file_metadata_fields,
                supportsAllDrives=True,
            )
            .execute()
        )

        docs = build("docs", "v1", credentials=self.creds, cache_discovery=False)
        docs.documents().batchUpdate(
            documentId=created["id"],
            body={
                "requests": [
                    {"insertText": {"location": {"index": 1}, "text": content}}
                ]
            },
        ).execute()

        return DriveFile.model_validate(created)

    def upload_pdf_from_text(
        self,
        *,
        title: str,
        text: str,
        folder_id: str | None = None,
    ) -> DriveFile:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        pdf_io = io.BytesIO()
        canvas_obj = canvas.Canvas(pdf_io, pagesize=letter)
        _, height = letter

        y = height - 72
        for line in (text or "").splitlines():
            canvas_obj.drawString(72, y, line[:1200])
            y -= 14
            if y < 72:
                canvas_obj.showPage()
                y = height - 72
        canvas_obj.save()
        pdf_io.seek(0)

        file_metadata: dict[str, Any] = {
            "name": f"{title}.pdf",
            "mimeType": DRIVE_API_CONFIG.pdf,
        }
        if folder_id:
            file_metadata["parents"] = [folder_id]

        media = MediaIoBaseUpload(
            pdf_io,
            mimetype=DRIVE_API_CONFIG.pdf,
            resumable=False,
        )
        created = (
            self.drive.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields=DRIVE_API_CONFIG.file_metadata_fields,
                supportsAllDrives=True,
            )
            .execute()
        )
        return DriveFile.model_validate(created)

    def _download_bytes(self, file_id: str) -> bytes:
        request = self.drive.files().get_media(fileId=file_id)
        file_handle = io.BytesIO()
        downloader = MediaIoBaseDownload(file_handle, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return file_handle.getvalue()

    def _export_bytes(self, file_id: str, export_mime: str) -> bytes:
        data = self.drive.files().export(fileId=file_id, mimeType=export_mime).execute()
        return (
            data if isinstance(data, (bytes, bytearray)) else bytes(str(data), "utf-8")
        )


def build_drive_credentials(
    *,
    access_token: str | None = None,
    scopes: list[str] | None = None,
) -> Any:
    """Build Drive credentials.

    Resolution order:
    1) Delegated user access token passed by the agent.
    2) ADC if DRIVE_USE_ADC / USE_ADC_FOR_DRIVE is enabled.
    3) Local OAuth if DRIVE_ALLOW_LOCAL_OAUTH / ALLOW_LOCAL_OAUTH is enabled.
    """

    scopes = scopes or DRIVE_API_CONFIG.read_scopes_list()

    if access_token:
        # Validate the token before using it
        validate_access_token(access_token, scopes)
        return Credentials(token=access_token, scopes=scopes)

    if _truthy(_first_set_env(DRIVE_AUTH_CONFIG.use_adc_env_names)):
        import google.auth

        creds, _ = google.auth.default(scopes=scopes)
        return creds

    if _truthy(_first_set_env(DRIVE_AUTH_CONFIG.allow_local_oauth_env_names)):
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow

        client_secrets_path = Path(
            _first_set_env(
                DRIVE_AUTH_CONFIG.oauth_client_secret_env_names,
                DRIVE_AUTH_CONFIG.default_client_secret_path,
            )
        )
        token_cache_path = Path(
            os.getenv(
                DRIVE_AUTH_CONFIG.token_cache_env,
                DRIVE_AUTH_CONFIG.default_token_cache_path,
            )
        )
        token_cache_path.parent.mkdir(parents=True, exist_ok=True)

        creds: Credentials | None = None
        if token_cache_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(token_cache_path), scopes=scopes
                )
            except Exception:
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not client_secrets_path.exists():
                    raise FileNotFoundError(
                        f"OAuth client secrets not found at {client_secrets_path}. "
                        "Set one of the configured Drive OAuth client-secret environment variables."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(client_secrets_path), scopes=scopes
                )
                creds = flow.run_local_server(port=0)
            token_cache_path.write_text(creds.to_json(), encoding="utf-8")

        if creds is None:
            raise RuntimeError("Local OAuth flow did not return credentials.")
        return creds

    raise RuntimeError(
        "No Drive credentials available. Provide a delegated user access token header, "
        "or enable one of the ADC flags, or enable one of the local OAuth flags."
    )


def validate_access_token(
    access_token: str, required_scopes: list[str] | None = None
) -> dict[str, Any]:
    """Validate the access token against Google's tokeninfo endpoint.

    Args:
        access_token: The OAuth2 access token to validate.
        required_scopes: Optional list of scopes that the token must have.

    Returns:
        The token info dictionary if valid.

    Raises:
        AuthenticationError: If the token is invalid or missing required scopes.
    """
    import requests

    try:
        response = requests.get(
            DRIVE_AUTH_CONFIG.google_token_info_url_v3,
            params={"access_token": access_token},
            timeout=10,
        )
    except Exception as exc:
        raise AuthenticationError(f"Failed to reach token validation endpoint: {exc}")

    if response.status_code != 200:
        try:
            error_detail = response.json().get("error_description", response.text)
        except Exception:
            error_detail = response.text
        raise AuthenticationError(f"Invalid OAuth token: {error_detail}")

    token_info = response.json()

    if required_scopes:
        token_scopes = token_info.get("scope", "").split()
        missing = [s for s in required_scopes if s not in token_scopes]
        if missing:
            raise AuthenticationError(
                f"Token is missing required scopes: {', '.join(missing)}"
            )

    return token_info


def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text)
        return "\n\n".join(parts).strip()
    except Exception as exc:
        return f"[PDF_TEXT_EXTRACTION_FAILED: {type(exc).__name__}: {exc}]"


def _escape_q(value: str) -> str:
    return (value or "").replace("'", "\\'")


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _first_set_env(env_names: Sequence[str], default: str | None = None) -> str | None:
    for env_name in env_names:
        value = os.getenv(env_name)
        if value not in (None, ""):
            return value
    return default
