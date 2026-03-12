from typing import Union, Optional, List, Dict, Any
import logging
import mimetypes
import os
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GCSManager:
    """
    Manager for Google Cloud Storage operations.
    Initializes a storage client using Application Default Credentials (ADC)
    and provides methods for bucket and object management as per Issue #5.
    """

    def __init__(self):
        try:
            # Initializes client using Google Application Default Credentials (ADC)
            self.client = storage.Client()
            logger.info("GCS Client initialized successfully using ADC.")
        except GoogleCloudError as e:
            logger.error(f"Failed to initialize GCS Client: {e}")
            raise

    def get_bucket(self, bucket_name: str) -> storage.Bucket:
        """
        Retrieves a GCS bucket.

        Args:
            bucket_name: The name of the bucket to retrieve.

        Returns:
            storage.Bucket: The retrieved bucket object.
        """
        try:
            bucket = self.client.get_bucket(bucket_name)
            return bucket
        except GoogleCloudError as e:
            logger.error(f"Error retrieving bucket {bucket_name}: {e}")
            raise

    def create_bucket(self, bucket_name: str, location: str = "US") -> str:
        """
        Creates a new bucket in GCS.

        Args:
            bucket_name: The name of the bucket to create.
            location: The GCS location for the bucket (default: "US").

        Returns:
            str: The name of the created bucket.
        """
        try:
            bucket = self.client.create_bucket(bucket_name, location=location)
            logger.info(f"Bucket {bucket.name} created in {location}.")
            return bucket.name
        except GoogleCloudError as e:
            logger.error(f"Error creating bucket {bucket_name}: {e}")
            raise

    def update_bucket_labels(
        self, bucket_name: str, labels: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Updates the labels for an existing bucket.

        Args:
            bucket_name: The name of the bucket.
            labels: A dictionary of labels to set.

        Returns:
            Dict[str, str]: The updated labels dictionary.
        """
        try:
            bucket = self.get_bucket(bucket_name)
            bucket.labels = labels
            bucket.patch()
            logger.info(f"Labels updated for bucket {bucket_name}.")
            return bucket.labels
        except GoogleCloudError as e:
            logger.error(f"Error updating labels for bucket {bucket_name}: {e}")
            raise

    def create_object(
        self,
        bucket_name: str,
        object_name: str,
        content: Optional[Union[str, bytes]] = None,
        local_path: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> storage.Blob:
        """
        Uploads an object to a GCS bucket. Supports string/bytes content or local file paths.

        Args:
            bucket_name: The name of the destination bucket.
            object_name: The name of the object to create in the bucket.
            content: Text or binary content to upload.
            local_path: Path to a local file to upload.
            content_type: MIME type for the object. If not provided, it's auto-detected.

        Returns:
            storage.Blob: The created blob object.
        """
        try:
            bucket = self.get_bucket(bucket_name)
            blob = bucket.blob(object_name)

            # Determine content type if not provided
            if not content_type:
                if local_path:
                    content_type, _ = mimetypes.guess_type(local_path)
                elif object_name:
                    content_type, _ = mimetypes.guess_type(object_name)

            if local_path:
                if not os.path.exists(local_path):
                    raise FileNotFoundError(f"Local file not found: {local_path}")
                blob.upload_from_filename(local_path, content_type=content_type)
                logger.info(
                    f"File {local_path} uploaded as {object_name} to bucket {bucket_name}."
                )
            elif content is not None:
                if isinstance(content, str):
                    blob.upload_from_string(
                        content, content_type=content_type or "text/plain"
                    )
                else:
                    blob.upload_from_string(
                        content, content_type=content_type or "application/octet-stream"
                    )
                logger.info(f"Object {object_name} created in bucket {bucket_name}.")
            else:
                raise ValueError("Either content or local_path must be provided.")

            return blob
        except (GoogleCloudError, FileNotFoundError, ValueError) as e:
            logger.error(
                f"Error creating object {object_name} in bucket {bucket_name}: {e}"
            )
            raise

    def download_object_as_bytes(self, bucket_name: str, object_name: str) -> bytes:
        """
        Downloads an object from GCS and returns its content as bytes.

        Args:
            bucket_name: The name of the bucket.
            object_name: The name of the object to download.

        Returns:
            bytes: The downloaded content.
        """
        try:
            bucket = self.get_bucket(bucket_name)
            blob = bucket.blob(object_name)
            content = blob.download_as_bytes()
            logger.info(f"Object {object_name} downloaded from bucket {bucket_name}.")
            return content
        except GoogleCloudError as e:
            logger.error(
                f"Error downloading object {object_name} from bucket {bucket_name}: {e}"
            )
            raise

    def update_object_metadata(
        self, bucket_name: str, object_name: str, metadata: Dict[str, Any]
    ) -> storage.Blob:
        """
        Updates the metadata for an existing object (e.g., content_type, custom metadata).

        Args:
            bucket_name: The name of the bucket.
            object_name: The name of the object.
            metadata: A dictionary of metadata to update. Special keys: 'content_type'.

        Returns:
            storage.Blob: The updated blob object.
        """
        try:
            bucket = self.get_bucket(bucket_name)
            blob = bucket.get_blob(object_name)
            if not blob:
                raise ValueError(
                    f"Object {object_name} not found in bucket {bucket_name}."
                )

            if "content_type" in metadata:
                blob.content_type = metadata.pop("content_type")

            blob.metadata = {**(blob.metadata or {}), **metadata}
            blob.patch()
            logger.info(f"Metadata updated for object {object_name}.")
            return blob
        except (GoogleCloudError, ValueError) as e:
            logger.error(f"Error updating metadata for object {object_name}: {e}")
            raise

    def delete_object(self, bucket_name: str, object_name: str) -> bool:
        """
        Deletes an object from a bucket.

        Args:
            bucket_name: The name of the bucket.
            object_name: The name of the object to delete.

        Returns:
            bool: True if successful.
        """
        try:
            bucket = self.get_bucket(bucket_name)
            blob = bucket.blob(object_name)
            blob.delete()
            logger.info(f"Object {object_name} deleted from bucket {bucket_name}.")
            return True
        except GoogleCloudError as e:
            logger.error(
                f"Error deleting object {object_name} from bucket {bucket_name}: {e}"
            )
            raise

    def list_blobs(self, bucket_name: str, prefix: Optional[str] = None) -> List[str]:
        """
        Lists all blobs in a bucket (optionally filtering by prefix).

        Args:
            bucket_name: The name of the bucket.
            prefix: Optional prefix to filter results.

        Returns:
            List[str]: A list of blob names.
        """
        try:
            bucket = self.get_bucket(bucket_name)
            blobs = self.client.list_blobs(bucket, prefix=prefix)
            blob_names = [blob.name for blob in blobs]
            logger.info(f"Listed {len(blob_names)} blobs in bucket {bucket_name}.")
            return blob_names
        except GoogleCloudError as e:
            logger.error(f"Error listing blobs in bucket {bucket_name}: {e}")
            raise
