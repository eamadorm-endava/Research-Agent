"""Google Drive connector (RAG-ready).

This module contains a small wrapper around the Google Drive API (v3):
- List/search files
- Download/export content
- Extract text from common formats

It is designed to be called from ADK FunctionTools.
"""

from __future__ import annotations

from dataclasses import dataclass
import io
from typing import Any, Optional, Sequence

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from pypdf import PdfReader

GOOGLE_DOC = "application/vnd.google-apps.document"
GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
GOOGLE_SLIDE = "application/vnd.google-apps.presentation"
GOOGLE_FOLDER = "application/vnd.google-apps.folder"


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
        d = super().to_dict()
        d["text"] = self.text
        return d


class DriveConnector:
    """A thin wrapper around the Drive API."""

    def __init__(self, creds: Any):
        # `creds` can be google.oauth2.credentials.Credentials or other google.auth creds.
        self.creds = creds
        self.drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    # ---------- discovery helpers ----------

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
        """Search for files.

        Args:
            search_text: plain text; we translate into Drive query `(name contains ... or fullText contains ...)`.
            drive_query: raw Drive query language `q` string; if provided, overrides search_text.
            folder_id: restrict to a folder ("'id' in parents")
            mime_types: optional list of MIME types to include (OR-ed)
        """

        q_parts: list[str] = []

        if drive_query:
            q_parts.append(drive_query)
        else:
            st = (search_text or "").strip()
            if st:
                escaped = _escape_q(st)
                q_parts.append(f"(name contains '{escaped}' or fullText contains '{escaped}')")

        if folder_id:
            q_parts.append(f"'{_escape_q(folder_id)}' in parents")

        if mime_types:
            mime_filters = " or ".join([f"mimeType = '{_escape_q(m)}'" for m in mime_types])
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

    # ---------- content extraction ----------

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

        # Google Workspace docs: export
        if mime == GOOGLE_DOC:
            text = self._export_bytes(file_id, "text/plain").decode("utf-8", errors="ignore")
        elif mime == GOOGLE_SHEET:
            text = self._export_bytes(file_id, "text/csv").decode("utf-8", errors="ignore")
        elif mime == GOOGLE_SLIDE:
            # Slides export text/plain is not always supported; fallback to PDF.
            try:
                text = self._export_bytes(file_id, "text/plain").decode("utf-8", errors="ignore")
            except Exception:
                pdf_bytes = self._export_bytes(file_id, "application/pdf")
                text = _extract_text_from_pdf_bytes(pdf_bytes)

        else:
            # Non-Google formats: download
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

    # ---------- write-back helpers (optional) ----------

    def create_google_doc_from_text(
        self,
        *,
        title: str,
        content: str,
        folder_id: str | None = None,
    ) -> DriveFile:
        """Create a Google Doc and insert text.

        Requires scopes:
        - https://www.googleapis.com/auth/drive.file
        - https://www.googleapis.com/auth/documents
        """

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
            body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
        ).execute()

        return DriveFile(**created)

    def upload_pdf_from_text(
        self,
        *,
        title: str,
        text: str,
        folder_id: str | None = None,
    ) -> DriveFile:
        """Create a simple PDF from text and upload it to Drive.

        Requires scope:
        - https://www.googleapis.com/auth/drive.file
        """

        # Local PDF generation.
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter

        pdf_io = io.BytesIO()
        c = canvas.Canvas(pdf_io, pagesize=letter)
        _, height = letter

        y = height - 72
        for line in (text or "").splitlines():
            c.drawString(72, y, line[:1200])
            y -= 14
            if y < 72:
                c.showPage()
                y = height - 72
        c.save()
        pdf_io.seek(0)

        file_metadata: dict[str, Any] = {"name": f"{title}.pdf", "mimeType": "application/pdf"}
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

    # ---------- internal helpers ----------

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


def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts: list[str] = []
        for page in reader.pages:
            t = page.extract_text() or ""
            if t.strip():
                parts.append(t)
        return "\n\n".join(parts).strip()
    except Exception as e:
        return f"[PDF_TEXT_EXTRACTION_FAILED: {type(e).__name__}: {e}]"


def _escape_q(value: str) -> str:
    """Escape single quotes for Drive query strings."""
    return (value or "").replace("'", "\\'")
