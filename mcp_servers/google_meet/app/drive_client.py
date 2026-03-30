from __future__ import annotations

import logging
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .config import DRIVE_CONFIG

logger = logging.getLogger(__name__)


class DriveClient:
    """Stateless connector for Google Drive API.

    This client is used to resolve metadata for Meet recording and transcript files.
    """

    def __init__(self, creds: Credentials) -> None:
        self.creds = creds
        self.drive = build(
            DRIVE_CONFIG.drive_api_service_name,
            DRIVE_CONFIG.drive_api_version,
            credentials=creds,
            cache_discovery=False,
        )
        logger.info(
            f"Initialized DriveClient with Drive ({DRIVE_CONFIG.drive_api_version})"
        )

    def get_recording_metadata(self, file_id: str) -> dict[str, Any] | None:
        """Fetch metadata for a Drive file (recording or transcript).

        Args:
            file_id (str): The Google Drive file ID.

        Returns:
            dict | None: File metadata if successful, else None.
        """
        logger.info(f"Fetching metadata for Drive file ID: {file_id}")
        try:
            file_metadata = (
                self.drive.files()
                .get(fileId=file_id, fields="id, name, webViewLink")
                .execute()
            )
            logger.debug(f"Successfully retrieved metadata for file {file_id}")
            return file_metadata
        except Exception as exc:
            logger.warning(
                f"Failed to fetch Drive metadata for file {file_id}: {exc}",
                exc_info=True,
            )
            return None
