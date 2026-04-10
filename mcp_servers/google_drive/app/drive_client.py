from __future__ import annotations

import io
from pathlib import PurePosixPath
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional, Sequence
from xml.sax.saxutils import escape as xml_escape

import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .config import DRIVE_API_CONFIG, DRIVE_AUTH_CONFIG, DRIVE_PDF_CONFIG
from .schemas import (
    AuthenticationError,
    DriveDocumentModel as DriveTextDocument,
    DriveFileMetadata,
    DriveFileModel as DriveFile,
    DriveMimeType,
    ListFilesSortField,
    SortDirection,
)


class DriveManager:
    """Manager for Google Drive operations."""

    def __init__(self, creds: Credentials) -> None:
        self.creds = creds
        self.drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    def list_files(
        self,
        *,
        folder_name: Optional[str] = None,
        file_name: Optional[str] = None,
        mime_type: Optional[DriveMimeType] = None,
        creation_time: Optional[str] = None,
        last_update: Optional[str] = None,
        order_by: Optional[dict[ListFilesSortField, SortDirection]] = None,
        max_results: int = 10,
    ) -> list[DriveFileMetadata]:
        folder_id = (
            self._resolve_folder_id_by_path(folder_name) if folder_name else None
        )
        if folder_name and not folder_id:
            return []

        query_parts: list[str] = []
        if folder_id:
            query_parts.append(f"'{_escape_q(folder_id)}' in parents")
        if file_name:
            query_parts.append(f"name contains '{_escape_q(file_name.strip())}'")
        if mime_type:
            query_parts.append(f"mimeType = '{_escape_q(mime_type.value)}'")
        if creation_time:
            start_of_day = f"{creation_time}T00:00:00"
            end_of_day = (
                datetime.strptime(creation_time, "%Y-%m-%d") + timedelta(days=1)
            ).strftime("%Y-%m-%dT00:00:00")
            query_parts.append(f"createdTime >= '{start_of_day}'")
            query_parts.append(f"createdTime < '{end_of_day}'")
        if last_update:
            start_of_day = f"{last_update}T00:00:00"
            end_of_day = (
                datetime.strptime(last_update, "%Y-%m-%d") + timedelta(days=1)
            ).strftime("%Y-%m-%dT00:00:00")
            query_parts.append(f"modifiedTime >= '{start_of_day}'")
            query_parts.append(f"modifiedTime < '{end_of_day}'")

        query = " and ".join(part for part in query_parts if part) or None
        candidate_size = min(max(max_results * 10, 100), 1000)
        response = (
            self.drive.files()
            .list(
                q=query,
                pageSize=candidate_size,
                fields=DRIVE_API_CONFIG.file_list_fields,
                orderBy=self._build_drive_order_by(order_by),
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        files = self._build_drive_files(response.get("files", []))
        metadata_items = [self._to_list_file_metadata(item) for item in files]
        metadata_items = self._sort_list_file_metadata(metadata_items, order_by or {})
        return metadata_items[:max_results]

    def get_file_text(self, file_id: str) -> DriveTextDocument:
        metadata = self._get_file_metadata_payload(file_id)
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

        enriched_metadata = self._normalize_file_payload(metadata, path_cache={})
        return DriveTextDocument.model_validate(
            {
                **enriched_metadata,
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

        return self.get_file(created["id"])

    def upload_pdf_from_text(
        self,
        *,
        title: str,
        text: str,
        folder_id: Optional[str] = None,
    ) -> DriveFile:
        pdf_io = _build_pdf_bytes_from_text(text)

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
        return self.get_file(created["id"])

    def create_file(
        self,
        *,
        name: str,
        content: str = "",
        mime_type: str = DRIVE_API_CONFIG.plain_text,
        folder_id: Optional[str] = None,
    ) -> DriveFile:
        normalized_name = name.strip()
        if (
            mime_type == DRIVE_API_CONFIG.plain_text
            and "." not in PurePosixPath(normalized_name).name
        ):
            normalized_name = f"{normalized_name}.txt"

        file_metadata: dict[str, Any] = {
            "name": normalized_name,
            "mimeType": mime_type or DRIVE_API_CONFIG.plain_text,
        }
        if folder_id:
            file_metadata["parents"] = [folder_id]

        media_body = None
        if content:
            media_body = MediaIoBaseUpload(
                io.BytesIO(content.encode("utf-8")),
                mimetype=file_metadata["mimeType"],
                resumable=False,
            )

        created = (
            self.drive.files()
            .create(
                body=file_metadata,
                media_body=media_body,
                fields=DRIVE_API_CONFIG.file_metadata_fields,
                supportsAllDrives=True,
            )
            .execute()
        )
        return self.get_file(created["id"])

    def create_folder(
        self,
        *,
        name: str,
        folder_id: Optional[str] = None,
    ) -> DriveFile:
        file_metadata: dict[str, Any] = {
            "name": name,
            "mimeType": DRIVE_API_CONFIG.google_folder,
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
        return self.get_file(created["id"])

    def move_file(
        self,
        *,
        file_id: str,
        destination_folder_id: str,
    ) -> DriveFile:
        current = (
            self.drive.files()
            .get(
                fileId=file_id,
                fields="id,parents",
                supportsAllDrives=True,
            )
            .execute()
        )
        previous_parents = ",".join(current.get("parents", []))
        update_kwargs: dict[str, Any] = {
            "fileId": file_id,
            "addParents": destination_folder_id,
            "fields": DRIVE_API_CONFIG.file_metadata_fields,
            "supportsAllDrives": True,
        }
        if previous_parents:
            update_kwargs["removeParents"] = previous_parents

        self.drive.files().update(**update_kwargs).execute()
        return self.get_file(file_id)

    def rename_file(
        self,
        *,
        file_id: str,
        new_name: str,
    ) -> DriveFile:
        self.drive.files().update(
            fileId=file_id,
            body={"name": new_name},
            fields=DRIVE_API_CONFIG.file_metadata_fields,
            supportsAllDrives=True,
        ).execute()
        return self.get_file(file_id)

    def get_file(self, file_id: str) -> DriveFile:
        metadata = self._get_file_metadata_payload(file_id)
        normalized = self._normalize_file_payload(metadata, path_cache={})
        return DriveFile.model_validate(normalized)

    def _to_list_file_metadata(self, file_payload: DriveFile) -> DriveFileMetadata:
        owner = file_payload.owners[0] if file_payload.owners else None
        full_path = file_payload.path or f"/{file_payload.name}"
        folder_path = str(PurePosixPath(full_path).parent)
        if folder_path == ".":
            folder_path = "/"
        return DriveFileMetadata.model_validate(
            {
                "creation_at": file_payload.createdTime,
                "last_update_at": file_payload.modifiedTime,
                "folder_path": folder_path,
                "file_name": file_payload.name,
                "file_id": file_payload.id,
                "created_by": {
                    "name": getattr(owner, "displayName", None) if owner else None,
                    "email": getattr(owner, "emailAddress", None) if owner else None,
                },
                "mime_type": file_payload.mimeType,
            }
        )

    def _sort_list_file_metadata(
        self,
        items: list[DriveFileMetadata],
        order_by: dict[ListFilesSortField, SortDirection],
    ) -> list[DriveFileMetadata]:
        if not order_by:
            return items

        sort_key_map = {
            ListFilesSortField.FOLDER_NAME: lambda item: (
                item.folder_path or ""
            ).lower(),
            ListFilesSortField.FILE_NAME: lambda item: (item.file_name or "").lower(),
            ListFilesSortField.CREATION_TIME: lambda item: item.creation_at or "",
            ListFilesSortField.LAST_UPDATE: lambda item: item.last_update_at or "",
        }

        sorted_items = list(items)
        for field, direction in reversed(list(order_by.items())):
            reverse = direction == SortDirection.DESC
            sorted_items.sort(key=sort_key_map[field], reverse=reverse)
        return sorted_items

    def _build_drive_order_by(
        self,
        order_by: Optional[dict[ListFilesSortField, SortDirection]],
    ) -> str:
        if not order_by:
            return DRIVE_API_CONFIG.order_by

        drive_order_map = {
            ListFilesSortField.FILE_NAME: "name_natural",
            ListFilesSortField.CREATION_TIME: "createdTime",
            ListFilesSortField.LAST_UPDATE: "modifiedTime",
        }
        order_parts = []
        for field, direction in order_by.items():
            mapped = drive_order_map.get(field)
            if not mapped:
                continue
            order_parts.append(f"{mapped} {direction.value}")
        return ", ".join(order_parts) or DRIVE_API_CONFIG.order_by

    def _resolve_folder_id_by_path(self, folder_path: str) -> Optional[str]:
        normalized_path = folder_path.strip().strip("/")
        if not normalized_path:
            return None

        current_parent_id: Optional[str] = None
        for segment in [part for part in normalized_path.split("/") if part]:
            query_parts = [
                f"name = '{_escape_q(segment)}'",
                f"mimeType = '{DRIVE_API_CONFIG.google_folder}'",
                "trashed = false",
            ]
            if current_parent_id:
                query_parts.append(f"'{_escape_q(current_parent_id)}' in parents")
            query = " and ".join(query_parts)
            response = (
                self.drive.files()
                .list(
                    q=query,
                    pageSize=1,
                    fields="files(id,name,parents)",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            matches = response.get("files", [])
            if not matches:
                return None
            current_parent_id = matches[0]["id"]
        return current_parent_id

    def _build_drive_files(
        self, files_payload: Sequence[Mapping[str, Any]]
    ) -> list[DriveFile]:
        path_cache: dict[str, dict[str, Any]] = {}
        return [
            DriveFile.model_validate(
                self._normalize_file_payload(file_payload, path_cache=path_cache)
            )
            for file_payload in files_payload
        ]

    def _normalize_file_payload(
        self,
        file_payload: Mapping[str, Any],
        *,
        path_cache: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        normalized = dict(file_payload)
        normalized["parents"] = list(normalized.get("parents") or [])
        normalized["owners"] = list(normalized.get("owners") or [])
        if normalized.get("size") not in (None, ""):
            normalized["size"] = int(normalized["size"])
        if normalized.get("version") not in (None, ""):
            normalized["version"] = int(normalized["version"])
        normalized["path"] = self._resolve_path(normalized, path_cache=path_cache)
        return normalized

    def _resolve_path(
        self,
        file_payload: Mapping[str, Any],
        *,
        path_cache: dict[str, dict[str, Any]],
    ) -> str:
        names = [str(file_payload.get("name") or "").strip()]
        current_parent = next(iter(file_payload.get("parents") or []), None)
        visited = {str(file_payload.get("id") or "")}

        while current_parent and current_parent not in visited:
            visited.add(current_parent)
            parent_payload = path_cache.get(current_parent)
            if parent_payload is None:
                parent_payload = (
                    self.drive.files()
                    .get(
                        fileId=current_parent,
                        fields=DRIVE_API_CONFIG.path_resolution_fields,
                        supportsAllDrives=True,
                    )
                    .execute()
                )
                path_cache[current_parent] = {
                    "id": parent_payload.get("id"),
                    "name": parent_payload.get("name"),
                    "parents": list(parent_payload.get("parents") or []),
                }
            parent_name = str(parent_payload.get("name") or "").strip()
            if parent_name:
                names.append(parent_name)
            current_parent = next(iter(parent_payload.get("parents") or []), None)

        parts = [part for part in reversed(names) if part]
        return "/" + "/".join(parts) if parts else "/"

    def _get_file_metadata_payload(self, file_id: str) -> dict[str, Any]:
        return (
            self.drive.files()
            .get(
                fileId=file_id,
                fields=DRIVE_API_CONFIG.file_metadata_fields,
                supportsAllDrives=True,
            )
            .execute()
        )

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
    access_token: Optional[str] = None,
    scopes: Optional[Sequence[str]] = None,
    validate: bool = True,
) -> Credentials:
    scopes = scopes or DRIVE_API_CONFIG.read_scopes

    if access_token:
        if validate:
            validate_access_token(access_token, scopes)
        return Credentials(token=access_token, scopes=scopes)

    raise RuntimeError(
        "No Drive credentials available. Provide a delegated user access token header."
    )


def validate_access_token(
    access_token: str, required_scopes: Optional[Sequence[str]] = None
) -> dict[str, Any]:
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
        token_scopes = set(token_info.get("scope", "").split())
        if DRIVE_API_CONFIG.drive_scope in token_scopes:
            token_scopes.update(
                {
                    DRIVE_API_CONFIG.drive_scope,
                    "https://www.googleapis.com/auth/drive.readonly",
                    "https://www.googleapis.com/auth/drive.file",
                    "https://www.googleapis.com/auth/documents",
                }
            )
        missing = [scope for scope in required_scopes if scope not in token_scopes]
        if missing:
            raise AuthenticationError(
                f"Token is missing required scopes: {', '.join(missing)}"
            )

    return token_info


def _build_pdf_bytes_from_text(text: str) -> io.BytesIO:
    pdf_io = io.BytesIO()
    document = SimpleDocTemplate(
        pdf_io,
        pagesize=letter,
        leftMargin=DRIVE_PDF_CONFIG.left_margin,
        rightMargin=DRIVE_PDF_CONFIG.right_margin,
        topMargin=DRIVE_PDF_CONFIG.top_margin,
        bottomMargin=DRIVE_PDF_CONFIG.bottom_margin,
    )
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        name="DriveGeneratedBody",
        parent=styles["BodyText"],
        fontName=DRIVE_PDF_CONFIG.font_name,
        fontSize=DRIVE_PDF_CONFIG.font_size,
        leading=DRIVE_PDF_CONFIG.leading,
        spaceAfter=DRIVE_PDF_CONFIG.paragraph_spacing,
    )

    normalized_text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    blocks = normalized_text.split("\n\n") if normalized_text else [""]
    story = []
    for block in blocks:
        lines = [xml_escape(line) for line in block.splitlines()] or [""]
        story.append(Paragraph("<br/>".join(lines), body_style))
        story.append(Spacer(1, DRIVE_PDF_CONFIG.paragraph_spacing))

    document.build(story)
    pdf_io.seek(0)
    return pdf_io


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
