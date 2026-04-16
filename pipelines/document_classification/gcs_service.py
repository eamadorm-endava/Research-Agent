from google.cloud import storage
from loguru import logger
import os


class GCSService:
    """Service class for GCS file operations: routing, moving, and metadata extraction.

    Handles the physical relocation of files across domain buckets and extraction
     of custom metadata (x-goog-meta-*) used in the classification process.
    """

    def __init__(self):
        """Initializes the GCS client using Application Default Credentials (ADC)."""
        self.client = storage.Client()

    def get_blob_metadata(self, gcs_uri: str) -> dict:
        """Extracts custom metadata and properties from a GCS blob.

        Args:
            gcs_uri (str): URI of the blob (gs://bucket/object).

        Returns:
            dict: Dictionary with 8 fields required by Step 01.
        """
        logger.info(f"Extracting detailed GCS metadata for: {gcs_uri}")
        bucket_name, blob_name = self._parse_uri(gcs_uri)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.get_blob(blob_name)

        if not blob:
            raise FileNotFoundError(f"Blob not found: {gcs_uri}")

        # Extract from custom metadata (x-goog-meta-*) or provide defaults
        custom = blob.metadata if blob.metadata else {}

        return {
            "filename": os.path.basename(blob.name),
            "mime_type": blob.content_type or "application/octet-stream",
            "proposed_domain": custom.get("domain", "it"),
            "trust_level": custom.get("trust-level", "wip"),
            "project_name": custom.get("project", "unknown"),
            "uploader_email": custom.get("uploader", "system"),
            "creator_name": custom.get("creator-name")
            or (blob.owner.get("entity") if isinstance(blob.owner, dict) else "system"),
            "ingested_at": blob.time_created.isoformat() if blob.time_created else None,
        }

    def download_blob_bytes(self, gcs_uri: str) -> bytes:
        """Downloads the content of a GCS blob as bytes.

        Args:
            gcs_uri (str): GCS URI.

        Returns:
            bytes: Content of the blob.
        """
        bucket_name, blob_name = self._parse_uri(gcs_uri)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        return blob.download_as_bytes()

    def upload_blob_bytes(self, gcs_uri: str, data: bytes, content_type: str) -> str:
        """Uploads bytes to a GCS destination.

        Args:
            gcs_uri (str): Destination URI.
            data (bytes): Content to upload.
            content_type (str): MIME type.

        Returns:
            str: Destination URI.
        """
        bucket_name, blob_name = self._parse_uri(gcs_uri)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(data, content_type=content_type)
        return gcs_uri

    def _parse_uri(self, gcs_uri: str) -> tuple[str, str]:
        """Helper to split gs://bucket/path into (bucket, path)."""
        if not gcs_uri.startswith("gs://"):
            raise ValueError("Invalid GCS URI")

        parts = gcs_uri[5:].split("/", 1)
        if len(parts) < 2:
            raise ValueError("Incomplete GCS URI")

        return parts[0], parts[1]
