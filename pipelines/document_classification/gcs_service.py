from google.cloud import storage
from loguru import logger
import os
from .config import EKB_CONFIG


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
            dict: Dictionary with extracted metadata.
        """
        logger.info(f"Extracting GCS metadata for: {gcs_uri}")
        bucket_name, blob_name = self._parse_uri(gcs_uri)

        bucket = self.client.bucket(bucket_name)
        blob = bucket.get_blob(blob_name)

        if not blob:
            raise FileNotFoundError(f"File not found: {gcs_uri}")

        metadata = {
            "project": blob.metadata.get("project", "unknown")
            if blob.metadata
            else "unknown",
            "trust_level": blob.metadata.get("trust-level", "wip")
            if blob.metadata
            else "wip",
            "uploader_email": blob.metadata.get("uploader", "system")
            if blob.metadata
            else "system",
            "filename": os.path.basename(blob.name),
            "content_type": blob.content_type,
        }

        return metadata

    def ensure_bucket_exists(self, bucket_name: str) -> None:
        """Checks if a bucket exists; if not, creates it in the configured location.

        Args:
            bucket_name (str): The name of the bucket to verify.
        """
        bucket = self.client.bucket(bucket_name)
        if not bucket.exists():
            logger.info(
                f"Bucket {bucket_name} not found. Creating in {EKB_CONFIG.LOCATION}..."
            )
            # Create bucket with default settings in the specified location
            self.client.create_bucket(bucket, location=EKB_CONFIG.LOCATION)
            logger.info(f"Bucket {bucket_name} created successfully.")

    def move_blob(self, source_uri: str, destination_uri: str) -> str:
        """Moves a blob from a source URI to a destination URI.

        Args:
            source_uri (str): Source GCS URI.
            destination_uri (str): Destination GCS URI.

        Returns:
            str: The final GCS URI of the moved file.
        """
        logger.info(f"Moving file: {source_uri} -> {destination_uri}")

        source_bucket_name, source_blob_name = self._parse_uri(source_uri)
        dest_bucket_name, dest_blob_name = self._parse_uri(destination_uri)

        # Ensure target bucket exists before copying
        self.ensure_bucket_exists(dest_bucket_name)

        source_bucket = self.client.bucket(source_bucket_name)
        source_blob = source_bucket.blob(source_blob_name)
        dest_bucket = self.client.bucket(dest_bucket_name)

        # Copy to destination then delete source
        source_bucket.copy_blob(source_blob, dest_bucket, dest_blob_name)
        source_blob.delete()

        logger.info(f"File successfully moved to: {destination_uri}")
        return destination_uri

    def upload_masked_copy(self, source_uri: str, masked_content: str) -> str:
        """Uploads a temporary masked copy for LLM analysis.

        Args:
            source_uri (str): Original URI (to derive path).
            masked_content (str): The de-identified content.

        Returns:
            str: URI of the temporary masked copy.
        """
        bucket_name, blob_name = self._parse_uri(source_uri)
        temp_blob_name = f"temp_masked/{os.path.basename(blob_name)}"

        # Ensure landing zone bucket exists (though it should)
        self.ensure_bucket_exists(bucket_name)

        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(temp_blob_name)
        blob.upload_from_string(masked_content, content_type="text/plain")

        return f"gs://{bucket_name}/{temp_blob_name}"

    def _parse_uri(self, gcs_uri: str) -> tuple[str, str]:
        """Helper to split gs://bucket/path into (bucket, path)."""
        if not gcs_uri.startswith("gs://"):
            raise ValueError("Invalid GCS URI")

        parts = gcs_uri[5:].split("/", 1)
        if len(parts) < 2:
            raise ValueError("Incomplete GCS URI")

        return parts[0], parts[1]
