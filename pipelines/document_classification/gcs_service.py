from google.cloud import storage
from loguru import logger
from .schemas import DocumentMetadata


class GCSService:
    """Service class for GCS file operations: routing, moving, and metadata extraction.

    Handles the physical relocation of files across domain buckets and extraction
    of custom metadata (x-goog-meta-*) used in the classification process.
    """

    def __init__(self) -> None:
        """Initializes the GCS client using Application Default Credentials (ADC).

        Returns:
            None
        """
        self.client = storage.Client()

    def get_blob_metadata(self, gcs_uri: str) -> DocumentMetadata:
        """Extracts custom metadata and properties from a GCS blob.
        Converts raw GCS metadata into a structured DocumentMetadata model.

        Args:
            gcs_uri (str): URI of the blob (gs://bucket/object).

        Returns:
            DocumentMetadata: Structured metadata containing 8 required fields.
        """
        logger.info(f"Extracting detailed GCS metadata for: {gcs_uri}")
        uri_parts = self._parse_uri(gcs_uri)
        bucket = self.client.bucket(uri_parts["bucket_name"])
        blob = bucket.get_blob(uri_parts["blob_name"])

        if not blob:
            raise FileNotFoundError(f"Blob not found: {gcs_uri}")

        # Extract from custom metadata (x-goog-meta-*) or provide defaults
        metadata_dict = blob.metadata if blob.metadata else {}

        return DocumentMetadata(
            filename=blob.name.split("/")[-1].split(".")[0],
            mime_type=blob.content_type or "application/octet-stream",
            proposed_domain=metadata_dict.get("domain", "unknown"),
            trust_level=metadata_dict.get("trust-level", "unknown"),
            project_name=metadata_dict.get("project", "unknown"),
            uploader_email=metadata_dict.get("uploader", "unknown"),
            creator_name=metadata_dict.get("creator-name", "unknown")
            or (
                blob.owner.get("entity") if isinstance(blob.owner, dict) else "unknown"
            ),
            ingested_at=blob.time_created.isoformat() if blob.time_created else None,
        )

    def download_blob_bytes(self, gcs_uri: str) -> bytes:
        """Downloads the content of a GCS blob as bytes.
        Retrieves the raw buffer for local processing (e.g., PDF splitting).

        Args:
            gcs_uri (str): GCS URI.

        Returns:
            bytes: Content of the blob.
        """
        uri_parts = self._parse_uri(gcs_uri)
        bucket = self.client.bucket(uri_parts["bucket_name"])
        blob = bucket.blob(uri_parts["blob_name"])
        return blob.download_as_bytes()

    def upload_blob_bytes(self, gcs_uri: str, data: bytes, content_type: str) -> str:
        """Uploads bytes to a GCS destination.
        Writes the processed (masked) content back to a new GCS object.

        Args:
            gcs_uri (str): Destination URI.
            data (bytes): Content to upload.
            content_type (str): MIME type.

        Returns:
            str: Destination URI of the uploaded blob.
        """
        uri_parts = self._parse_uri(gcs_uri)
        bucket = self.client.bucket(uri_parts["bucket_name"])
        blob = bucket.blob(uri_parts["blob_name"])
        blob.upload_from_string(data, content_type=content_type)
        return gcs_uri

    def _parse_uri(self, gcs_uri: str) -> dict[str, str]:
        """Helper to split gs://bucket/path into dictionary components.
        Ensures the URI follows the expected gs:// protocol format.

        Args:
            gcs_uri (str): The raw GCS URI.

        Returns:
            dict[str, str]: A dictionary containing '"bucket_name"' and '"blob_name"'.
        """
        logger.debug(f"Parsing GCS URI into dictionary: {gcs_uri}")
        if not gcs_uri.startswith("gs://"):
            raise ValueError("Invalid GCS URI")

        uri_split = gcs_uri[5:].split("/", 1)
        if len(uri_split) < 2:
            raise ValueError("Incomplete GCS URI")

        return {"bucket_name": uri_split[0], "blob_name": uri_split[1]}
