import time
from typing import Any, Callable, TypeVar
from google.cloud import storage
from loguru import logger
from .schemas import DocumentMetadata
from .config import gcs_config

GCSOperationResult = TypeVar("GCSOperationResult")


# Global client to share connection pool across multiple requests
gcs_client = storage.Client()


class GCSService:
    """Service class for GCS file operations: routing, moving, and metadata extraction.

    Handles the physical relocation of files across domain buckets and extraction
    of custom metadata (x-goog-meta-*) used in the classification process.
    """

    client = gcs_client

    def _execute_with_exponential_backoff(
        self, operation: Callable[..., GCSOperationResult], *args: Any, **kwargs: Any
    ) -> GCSOperationResult:
        """Executes a GCS operation with an exponential backoff retry strategy.

        This helper handles transient network errors and SSL connection drops
        (like SSLEOFError) by retrying the operation up to 3 times.

        Args:
            operation: Callable[..., GCSOperationResult] -> The GCS method to execute.
            *args: Any -> Positional arguments for the operation.
            **kwargs: Any -> Keyword arguments for the operation.

        Returns:
            GCSOperationResult -> The result of the successful operation.

        Raises:
            Exception: If the operation fails after all retry attempts.
        """
        for attempt in range(gcs_config.MAX_RETRIES):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                if attempt == gcs_config.MAX_RETRIES - 1:
                    logger.error(
                        f"GCS operation failed after {gcs_config.MAX_RETRIES} attempts: {str(e)}"
                    )
                    raise e

                wait_time = gcs_config.BASE_DELAY**attempt
                logger.warning(
                    f"GCS attempt {attempt + 1} failed: {str(e)}. Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)

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

        blob = self._execute_with_exponential_backoff(
            bucket.get_blob, uri_parts["blob_name"]
        )

        if not blob:
            raise FileNotFoundError(f"Blob not found: {gcs_uri}")

        # Extract from custom metadata (x-goog-meta-*) or provide defaults
        metadata_dict = blob.metadata if blob.metadata else {}

        return DocumentMetadata(
            filename=blob.name.split("/")[-1],
            mime_type=blob.content_type or "application/octet-stream",
            proposed_domain=metadata_dict.get("domain"),
            trust_level=metadata_dict.get("trust-level"),
            project_name=metadata_dict.get("project"),
            uploader_email=metadata_dict.get("uploader"),
            creator_name=metadata_dict.get("creator-name"),
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
        return self._execute_with_exponential_backoff(blob.download_as_bytes)

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
        self._execute_with_exponential_backoff(
            blob.upload_from_string, data, content_type=content_type
        )
        return gcs_uri

    def copy_blob(self, source_uri: str, destination_uri: str) -> str:
        """Copies a blob from a source URI to a destination URI.

        Args:
            source_uri (str): Source GCS URI.
            destination_uri (str): Destination GCS URI.

        Returns:
            str: The destination URI.
        """
        logger.info(f"Copying blob from {source_uri} to {destination_uri}")
        src_parts = self._parse_uri(source_uri)
        dst_parts = self._parse_uri(destination_uri)

        src_bucket = self.client.bucket(src_parts["bucket_name"])
        src_blob = src_bucket.blob(src_parts["blob_name"])
        dst_bucket = self.client.bucket(dst_parts["bucket_name"])

        self._execute_with_exponential_backoff(
            src_bucket.copy_blob, src_blob, dst_bucket, dst_parts["blob_name"]
        )
        return destination_uri

    def delete_blob(self, gcs_uri: str) -> None:
        """Deletes a blob from GCS.

        Args:
            gcs_uri (str): GCS URI of the blob to delete.

        Returns:
            None
        """
        logger.info(f"Deleting blob: {gcs_uri}")
        uri_parts = self._parse_uri(gcs_uri)
        bucket = self.client.bucket(uri_parts["bucket_name"])
        blob = bucket.blob(uri_parts["blob_name"])
        self._execute_with_exponential_backoff(blob.delete)

    def grant_iam_conditional_binding(
        self, bucket_name: str, folder_prefix: str, uploader_email: str
    ) -> None:
        """Grants roles/storage.objectAdmin to the uploader on their folder in the domain bucket.

        Uses a folder-level IAM condition (startsWith) so the single binding covers all current
        and future files the uploader stores in that project/tier path. Skips silently if the
        exact binding already exists.

        Args:
            bucket_name (str): Domain bucket name (e.g. "kb-it").
            folder_prefix (str): Object path prefix for the user folder
                (e.g. "project alpha/client-confidential/eamadorm11/").
            uploader_email (str): Email address to receive the binding.

        Returns:
            None
        """
        logger.info(
            f"Granting roles/storage.objectAdmin to {uploader_email} "
            f"on gs://{bucket_name}/{folder_prefix}"
        )
        resource_prefix = f"projects/_/buckets/{bucket_name}/objects/{folder_prefix}"
        condition_expr = f'resource.name.startsWith("{resource_prefix}")'

        bucket = self.client.bucket(bucket_name)
        iam_policy = self._execute_with_exponential_backoff(
            bucket.get_iam_policy, requested_policy_version=3
        )
        iam_policy.version = 3

        already_granted = any(
            binding.get("role") == "roles/storage.objectAdmin"
            and f"user:{uploader_email}" in binding.get("members", set())
            and (binding.get("condition") or {}).get("expression") == condition_expr
            for binding in iam_policy.bindings
        )

        if already_granted:
            logger.debug(
                f"IAM binding already exists for '{uploader_email}' on '{resource_prefix}'"
            )
            return

        iam_policy.bindings.append(
            {
                "role": "roles/storage.objectAdmin",
                "members": {f"user:{uploader_email}"},
                "condition": {
                    "title": "uploader-folder-access",
                    "expression": condition_expr,
                },
            }
        )
        self._execute_with_exponential_backoff(bucket.set_iam_policy, iam_policy)
        logger.info(
            f"Granted roles/storage.objectAdmin to '{uploader_email}' on '{resource_prefix}'"
        )

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
