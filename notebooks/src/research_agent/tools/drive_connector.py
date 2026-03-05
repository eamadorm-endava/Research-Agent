        from __future__ import annotations
    from dataclasses import dataclass
    from typing import List, Optional
    import io

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
    from google.oauth2.credentials import Credentials

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

    @dataclass
    class DriveTextDocument(DriveFile):
        text: str = ""

    class DriveConnector:
        def __init__(self, creds: Credentials):
            self.creds = creds
            self.drive = build("drive", "v3", credentials=creds, cache_discovery=False)

        def list_files(self, page_size: int = 10, include_folders: bool = False) -> List[DriveFile]:
            q = None if include_folders else f"mimeType != '{GOOGLE_FOLDER}'"
            resp = self.drive.files().list(
                q=q,
                pageSize=page_size,
                fields="files(id,name,mimeType,modifiedTime,webViewLink)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            return [DriveFile(**f) for f in resp.get("files", [])]

        def search_files(self, query: str, page_size: int = 10, include_folders: bool = False) -> List[DriveFile]:
            q_parts = [query]
            if not include_folders:
                q_parts.append(f"mimeType != '{GOOGLE_FOLDER}'")
            q = " and ".join([p for p in q_parts if p])

            resp = self.drive.files().list(
                q=q,
                pageSize=page_size,
                fields="files(id,name,mimeType,modifiedTime,webViewLink)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            return [DriveFile(**f) for f in resp.get("files", [])]

        def _download_bytes(self, file_id: str) -> bytes:
            request = self.drive.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            return fh.getvalue()

        def _export_bytes(self, file_id: str, export_mime: str) -> bytes:
            data = self.drive.files().export(fileId=file_id, mimeType=export_mime).execute()
            return data if isinstance(data, (bytes, bytearray)) else bytes(str(data), "utf-8")

        def _extract_text_from_pdf_bytes(self, pdf_bytes: bytes) -> str:
            try:
                reader = PdfReader(io.BytesIO(pdf_bytes))
                parts = []
                for page in reader.pages:
                    t = page.extract_text() or ""
                    if t.strip():
                        parts.append(t)
                return "

".join(parts).strip()
            except Exception as e:
                return f"[PDF_TEXT_EXTRACTION_FAILED: {type(e).__name__}: {e}]"

        def get_file_text(self, file_id: str) -> DriveTextDocument:
            meta = self.drive.files().get(
                fileId=file_id,
                fields="id,name,mimeType,modifiedTime,webViewLink",
                supportsAllDrives=True,
            ).execute()
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
                    text = self._extract_text_from_pdf_bytes(pdf_bytes)

            else:
                raw = self._download_bytes(file_id)
                if mime == "application/pdf" or name.lower().endswith(".pdf"):
                    text = self._extract_text_from_pdf_bytes(raw)
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

        def create_google_doc_from_text(self, title: str, content: str, folder_id: Optional[str] = None) -> DriveFile:
            file_metadata = {"name": title, "mimeType": GOOGLE_DOC}
            if folder_id:
                file_metadata["parents"] = [folder_id]

            created = self.drive.files().create(
                body=file_metadata,
                fields="id,name,mimeType,modifiedTime,webViewLink",
                supportsAllDrives=True,
            ).execute()

            docs = build("docs", "v1", credentials=self.creds, cache_discovery=False)
            docs.documents().batchUpdate(
                documentId=created["id"],
                body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
            ).execute()

            return DriveFile(**created)

        def upload_pdf_from_text(self, title: str, text: str, folder_id: Optional[str] = None) -> DriveFile:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter

            pdf_io = io.BytesIO()
            c = canvas.Canvas(pdf_io, pagesize=letter)
            width, height = letter

            y = height - 72
            for line in text.splitlines():
                c.drawString(72, y, line[:1200])
                y -= 14
                if y < 72:
                    c.showPage()
                    y = height - 72
            c.save()
            pdf_io.seek(0)

            file_metadata = {"name": f"{title}.pdf", "mimeType": "application/pdf"}
            if folder_id:
                file_metadata["parents"] = [folder_id]

            media = MediaIoBaseUpload(pdf_io, mimetype="application/pdf", resumable=False)

            created = self.drive.files().create(
                body=file_metadata,
                media_body=media,
                fields="id,name,mimeType,modifiedTime,webViewLink",
                supportsAllDrives=True,
            ).execute()

            return DriveFile(**created)
