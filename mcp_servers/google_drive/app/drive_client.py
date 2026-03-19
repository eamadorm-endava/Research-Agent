from __future__ import annotations

import io
from typing import Any, Optional, Sequence

import httpx
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

    def __init__(self, creds: Any) -> None:
        """
        Initializes the DriveManager with Google API credentials.
        Args:
            creds: Valid Google OAuth2 credentials.
        Return: None
        """
        self.creds = creds
        self.drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    def list_files(
        self,
        *,
        max_results: int = 10,
        folder_id: Optional[str] = None,
        include_folders: bool = False,
    ) -> list[DriveFile]:
        """
        Lists files in a specific folder or the root directory.
        Args:
            max_results: Maximum number of files to return.
            folder_id: Optional ID of the parent folder to list.
            include_folders: Whether to include folders in the result list.
        Return: A list of DriveFile objects.
        """
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
        search_text: Optional[str] = None,
        drive_query: Optional[str] = None,
        max_results: int = 10,
        folder_id: Optional[str] = None,
        include_folders: bool = False,
        mime_types: Optional[Sequence[str]] = None,
    ) -> list[DriveFile]:
        """
        Searches for files based on text or a raw Drive query.
        Args:
            search_text: Text to search for in file names and content.
            drive_query: Raw Google Drive API query string.
            max_results: Maximum number of results to return.
            folder_id: Optional folder ID to restrict the search.
            include_folders: Whether to include folders in the results.
            mime_types: Optional list of MIME types to filter by.
        Return: A list of DriveFile objects matching the criteria.
        """
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
        """
        Retrieves and extracts plain text from a Google Drive file.
        Args:
            file_id: The ID of the file to process.
        Return: A DriveTextDocument containing metadata and extracted text.
        """
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
        folder_id: Optional[str] = None,
    ) -> DriveFile:
        """
        Creates a new Google Doc and populates it with text.
        Args:
            title: The title of the new document.
            content: The plain text content to insert.
            folder_id: Optional folder ID where the doc will be created.
        Return: A DriveFile object representing the new document.
        """
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
        folder_id: Optional[str] = None,
    ) -> DriveFile:
        """
        Generates a PDF from text and uploads it to Google Drive.
        Args:
            title: The title of the PDF file (excluding extension).
            text: The plain text content for the PDF.
            folder_id: Optional folder ID where the PDF will be uploaded.
        Return: A DriveFile object representing the uploaded PDF.
        """
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
        """
        Downloads the raw bytes of a file from Google Drive.
        Args:
            file_id: The ID of the file to download.
        Return: The raw bytes of the file content.
        """
        request = self.drive.files().get_media(fileId=file_id)
        file_handle = io.BytesIO()
        downloader = MediaIoBaseDownload(file_handle, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return file_handle.getvalue()

    def _export_bytes(self, file_id: str, export_mime: str) -> bytes:
        """
        Exports a Google Workspace file (e.g., Doc, Sheet) to a specific format.
        Args:
            file_id: The ID of the file to export.
            export_mime: The target MIME type for the export.
        Return: The exported file content as bytes.
        """
        data = self.drive.files().export(fileId=file_id, mimeType=export_mime).execute()
        return (
            data if isinstance(data, (bytes, bytearray)) else bytes(str(data), "utf-8")
        )


def build_drive_credentials(
    *,
    access_token: Optional[str] = None,
    scopes: Optional[Sequence[str]] = None,
    validate: bool = True,
) -> Any:
    """
    Builds Google OAuth2 credentials from a provided access token.
    Args:
        access_token: Optional OAuth2 access token.
        scopes: Optional list of scopes requested for the credentials.
        validate: Whether to validate the token against Google's API before building.
    Return: A Google Credentials object.
    """

    scopes = scopes or DRIVE_API_CONFIG.read_scopes

    if access_token:
        if validate:
            # Validate the token before using it
            validate_access_token(access_token, scopes)
        return Credentials(token=access_token, scopes=scopes)

    raise RuntimeError(
        "No Drive credentials available. Provide a delegated user access token header."
    )


def validate_access_token(
    access_token: str, required_scopes: Optional[Sequence[str]] = None
) -> dict[str, Any]:
    """
    Validates the access token against Google's tokeninfo endpoint.
    Args:
        access_token: The OAuth2 access token to validate.
        required_scopes: Optional list of scopes that the token must have.
    Return: The token info dictionary if valid.
    """
    try:
        with httpx.Client() as client:
            response = client.get(
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
    """
    Extracts plain text from raw PDF bytes using pypdf.
    Args:
        pdf_bytes: The raw content of the PDF file.
    Return: Extracted plain text or an error message if extraction fails.
    """
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
    """
    Escapes single quotes for use in Google Drive API query strings.
    Args:
        value: The string value to escape.
    Return: The escaped string.
    """
    return (value or "").replace("'", "\\'")
