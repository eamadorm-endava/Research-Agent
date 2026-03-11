from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from pypdf import PdfReader

GOOGLE_DOC = "application/vnd.google-apps.document"
GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
GOOGLE_SLIDE = "application/vnd.google-apps.presentation"
GOOGLE_FOLDER = "application/vnd.google-apps.folder"

READ_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/drive.readonly",
]
WRITE_DOC_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
]
WRITE_PDF_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/drive.file",
]


@dataclass
class DriveFile:
    id: str
    name: str
    mimeType: str
    modifiedTime: Optional[str] = None
    webViewLink: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "mimeType": self.mimeType,
            "modifiedTime": self.modifiedTime,
            "webViewLink": self.webViewLink,
        }


@dataclass
class DriveTextDocument(DriveFile):
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        out = super().to_dict()
        out["text"] = self.text
        return out


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
        q_parts: list[str] = []
        if folder_id:
            q_parts.append(f"'{_escape_q(folder_id)}' in parents")
        if not include_folders:
            q_parts.append(f"mimeType != '{GOOGLE_FOLDER}'")
        q = " and ".join(q_parts) if q_parts else None

        resp = (
            self.drive.files()
            .list(
                q=q,
                pageSize=max_results,
                fields="files(id,name,mimeType,modifiedTime,webViewLink)",
                orderBy="modifiedTime desc",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        return [DriveFile(**f) for f in resp.get("files", [])]

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
        q_parts: list[str] = []

        if drive_query:
            q_parts.append(drive_query)
        else:
            search_text = (search_text or "").strip()
            if search_text:
                escaped = _escape_q(search_text)
                q_parts.append(
                    f"(name contains '{escaped}' or fullText contains '{escaped}')"
                )

        if folder_id:
            q_parts.append(f"'{_escape_q(folder_id)}' in parents")

        if mime_types:
            mime_filters = " or ".join(
                [f"mimeType = '{_escape_q(mime_type)}'" for mime_type in mime_types]
            )
            q_parts.append(f"({mime_filters})")

        if not include_folders:
            q_parts.append(f"mimeType != '{GOOGLE_FOLDER}'")

        q = " and ".join([p for p in q_parts if p]) or None

        resp = (
            self.drive.files()
            .list(
                q=q,
                pageSize=max_results,
                fields="files(id,name,mimeType,modifiedTime,webViewLink)",
                orderBy="modifiedTime desc",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        return [DriveFile(**f) for f in resp.get("files", [])]

    def get_file_text(self, file_id: str) -> DriveTextDocument:
        meta = (
            self.drive.files()
            .get(
                fileId=file_id,
                fields="id,name,mimeType,modifiedTime,webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )

        mime = meta.get("mimeType", "")
        name = meta.get("name", "")
        text = ""

        if mime == GOOGLE_DOC:
            text = self._export_bytes(file_id, "text/plain").decode("utf-8", errors="ignore")
        elif mime == GOOGLE_SHEET:
            text = self._export_bytes(file_id, "text/csv").decode("utf-8", errors="ignore")
        elif mime == GOOGLE_SLIDE:
            try:
                text = self._export_bytes(file_id, "text/plain").decode("utf-8", errors="ignore")
            except Exception:
                pdf_bytes = self._export_bytes(file_id, "application/pdf")
                text = _extract_text_from_pdf_bytes(pdf_bytes)
        else:
            raw = self._download_bytes(file_id)
            if mime == "application/pdf" or name.lower().endswith(".pdf"):
                text = _extract_text_from_pdf_bytes(raw)
            else:
                text = raw.decode("utf-8", errors="ignore")

        return DriveTextDocument(
            id=meta["id"],
            name=meta.get("name", ""),
            mimeType=mime,
            modifiedTime=meta.get("modifiedTime"),
            webViewLink=meta.get("webViewLink"),
            text=text,
        )

    def create_google_doc_from_text(
        self,
        *,
        title: str,
        content: str,
        folder_id: str | None = None,
    ) -> DriveFile:
        file_metadata: dict[str, Any] = {"name": title, "mimeType": GOOGLE_DOC}
        if folder_id:
            file_metadata["parents"] = [folder_id]

        created = (
            self.drive.files()
            .create(
                body=file_metadata,
                fields="id,name,mimeType,modifiedTime,webViewLink",
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

        return DriveFile(**created)

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
            "mimeType": "application/pdf",
        }
        if folder_id:
            file_metadata["parents"] = [folder_id]

        media = MediaIoBaseUpload(pdf_io, mimetype="application/pdf", resumable=False)
        created = (
            self.drive.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id,name,mimeType,modifiedTime,webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
        return DriveFile(**created)

    def _download_bytes(self, file_id: str) -> bytes:
        request = self.drive.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return fh.getvalue()

    def _export_bytes(self, file_id: str, export_mime: str) -> bytes:
        data = self.drive.files().export(fileId=file_id, mimeType=export_mime).execute()
        return data if isinstance(data, (bytes, bytearray)) else bytes(str(data), "utf-8")


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

    scopes = scopes or READ_SCOPES

    if access_token:
        return Credentials(token=access_token, scopes=scopes)

    if _truthy(os.getenv("DRIVE_USE_ADC") or os.getenv("USE_ADC_FOR_DRIVE")):
        import google.auth

        creds, _ = google.auth.default(scopes=scopes)
        return creds

    if _truthy(os.getenv("DRIVE_ALLOW_LOCAL_OAUTH") or os.getenv("ALLOW_LOCAL_OAUTH")):
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow

        client_secrets_path = Path(
            os.getenv(
                "DRIVE_GOOGLE_OAUTH_CLIENT_SECRETS",
                os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS", "client_secret.json"),
            )
        )
        token_cache_path = Path(
            os.getenv("DRIVE_TOKEN_CACHE", str(Path(".cache") / "drive_token.json"))
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
                        "Set DRIVE_GOOGLE_OAUTH_CLIENT_SECRETS or GOOGLE_OAUTH_CLIENT_SECRETS."
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
        "or enable DRIVE_USE_ADC/USE_ADC_FOR_DRIVE, or enable DRIVE_ALLOW_LOCAL_OAUTH/ALLOW_LOCAL_OAUTH."
    )


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
