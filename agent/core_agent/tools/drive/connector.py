"""Google Drive connector (RAG-ready).

This module contains a small wrapper around the Google Drive API (v3):
- List/search files
- Download/export content
- Extract text from common formats

It is designed to be called from ADK FunctionTools.
"""

from __future__ import annotations

import io
from typing import Annotated, Any, Sequence

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader

from .config import DRIVE_MIME_TYPE_CONFIG, DRIVE_TOOL_RUNTIME_CONFIG

DRIVE_FILE_ID = Annotated[
    str,
    Field(min_length=1, description="Drive file ID."),
]
DRIVE_FILE_NAME = Annotated[
    str,
    Field(min_length=1, description="Display name of the file."),
]
DRIVE_FILE_MIME_TYPE = Annotated[
    str,
    Field(min_length=1, description="Drive MIME type."),
]
DRIVE_FILE_MODIFIED_TIME = Annotated[
    str | None,
    Field(default=None, description="Last modified time."),
]
DRIVE_FILE_WEB_VIEW_LINK = Annotated[
    str | None,
    Field(default=None, description="Browser URL for the file."),
]
DRIVE_DOCUMENT_TEXT = Annotated[
    str,
    Field(default="", description="Extracted text content."),
]


class DriveBaseModel(BaseModel):
    """Shared schema base for the in-process Drive connector."""

    model_config = ConfigDict(extra="forbid")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python")


class DriveFile(DriveBaseModel):
    id: DRIVE_FILE_ID
    name: DRIVE_FILE_NAME
    mimeType: DRIVE_FILE_MIME_TYPE
    modifiedTime: DRIVE_FILE_MODIFIED_TIME
    webViewLink: DRIVE_FILE_WEB_VIEW_LINK


class DriveTextDocument(DriveFile):
    text: DRIVE_DOCUMENT_TEXT


class DriveConnector:
    """A thin wrapper around the Drive API."""

    def __init__(self, creds: Any):
        self.creds = creds
        self.drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    def list_files(
        self,
        *,
        max_results: int = DRIVE_TOOL_RUNTIME_CONFIG.default_max_results,
        folder_id: str | None = None,
        include_folders: bool = False,
    ) -> list[DriveFile]:
        query_parts: list[str] = []
        if folder_id:
            query_parts.append(f"'{_escape_q(folder_id)}' in parents")
        if not include_folders:
            query_parts.append(f"mimeType != '{DRIVE_MIME_TYPE_CONFIG.google_folder}'")
        query = " and ".join(query_parts) if query_parts else None

        response = (
            self.drive.files()
            .list(
                q=query,
                pageSize=max_results,
                fields=DRIVE_MIME_TYPE_CONFIG.file_list_fields,
                orderBy=DRIVE_MIME_TYPE_CONFIG.order_by,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        return [DriveFile.model_validate(file_payload) for file_payload in response.get("files", [])]

    def search_files(
        self,
        *,
        search_text: str | None = None,
        drive_query: str | None = None,
        max_results: int = DRIVE_TOOL_RUNTIME_CONFIG.default_max_results,
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
            query_parts.append(f"mimeType != '{DRIVE_MIME_TYPE_CONFIG.google_folder}'")

        query = " and ".join([part for part in query_parts if part]) or None

        response = (
            self.drive.files()
            .list(
                q=query,
                pageSize=max_results,
                fields=DRIVE_MIME_TYPE_CONFIG.file_list_fields,
                orderBy=DRIVE_MIME_TYPE_CONFIG.order_by,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        return [DriveFile.model_validate(file_payload) for file_payload in response.get("files", [])]

    def get_file_text(self, file_id: str) -> DriveTextDocument:
        metadata = (
            self.drive.files()
            .get(
                fileId=file_id,
                fields=DRIVE_MIME_TYPE_CONFIG.file_metadata_fields,
                supportsAllDrives=True,
            )
            .execute()
        )

        mime_type = metadata.get("mimeType", "")
        file_name = metadata.get("name", "")
        extracted_text = ""

        if mime_type == DRIVE_MIME_TYPE_CONFIG.google_doc:
            extracted_text = self._export_bytes(
                file_id, DRIVE_MIME_TYPE_CONFIG.export_text_plain
            ).decode("utf-8", errors="ignore")
        elif mime_type == DRIVE_MIME_TYPE_CONFIG.google_sheet:
            extracted_text = self._export_bytes(
                file_id, DRIVE_MIME_TYPE_CONFIG.export_csv
            ).decode("utf-8", errors="ignore")
        elif mime_type == DRIVE_MIME_TYPE_CONFIG.google_slide:
            try:
                extracted_text = self._export_bytes(
                    file_id, DRIVE_MIME_TYPE_CONFIG.export_text_plain
                ).decode("utf-8", errors="ignore")
            except Exception:
                pdf_bytes = self._export_bytes(file_id, DRIVE_MIME_TYPE_CONFIG.pdf)
                extracted_text = _extract_text_from_pdf_bytes(pdf_bytes)
        else:
            raw_bytes = self._download_bytes(file_id)
            if mime_type == DRIVE_MIME_TYPE_CONFIG.pdf or file_name.lower().endswith(".pdf"):
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
            "mimeType": DRIVE_MIME_TYPE_CONFIG.google_doc,
        }
        if folder_id:
            file_metadata["parents"] = [folder_id]

        created = (
            self.drive.files()
            .create(
                body=file_metadata,
                fields=DRIVE_MIME_TYPE_CONFIG.file_metadata_fields,
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
            "mimeType": DRIVE_MIME_TYPE_CONFIG.pdf,
        }
        if folder_id:
            file_metadata["parents"] = [folder_id]

        media = MediaIoBaseUpload(
            pdf_io,
            mimetype=DRIVE_MIME_TYPE_CONFIG.pdf,
            resumable=False,
        )
        created = (
            self.drive.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields=DRIVE_MIME_TYPE_CONFIG.file_metadata_fields,
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
        return data if isinstance(data, (bytes, bytearray)) else bytes(str(data), "utf-8")



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
