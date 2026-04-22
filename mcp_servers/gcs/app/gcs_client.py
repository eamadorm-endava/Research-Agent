from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Union
import logging
import mimetypes
import os
import httpx
import google.auth
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from google.oauth2.credentials import Credentials

from .config import GCS_API_CONFIG, GCS_AUTH_CONFIG
from .schemas import AuthenticationError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def detect_default_project_id() -> Optional[str]:
    """Best-effort detection of the ambient GCP project ID."""
    try:
        _, project_id = google.auth.default()
        return project_id
    except DefaultCredentialsError:
        logger.debug("Unable to detect default GCP project ID from ADC.")
        return None
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.debug("Unexpected error while detecting default GCP project ID: %s", exc)
        return None


class GCSManager:
    """
    Manager for Google Cloud Storage operations.
    Initializes a storage client using delegated user credentials
    and provides methods for bucket and object management.
    """

    def __init__(self, creds: Credentials, default_project: Optional[str] = None):
        self.creds = creds
        self.default_project = default_project or detect_default_project_id()
        try:
            self.client = storage.Client(
                credentials=self.creds, project=self.default_project
            )
            logger.info(
                "GCS client initialized successfully using delegated user credentials "
                f"(Project: {self.client.project})."
            )
        except GoogleCloudError as e:
            logger.error(f"Failed to initialize GCS Client: {e}")
            raise

    def resolve_project_id(self, project_id: Optional[str] = None) -> str:
        """Resolves the effective GCP project ID for project-scoped operations."""
        resolved_project = project_id or self.default_project or self.client.project
        if not resolved_project:
            raise ValueError(
                "No GCP project ID is configured for GCS. Provide request.project_id "
                "or set GCS_PROJECT_ID, PROJECT_ID, or GOOGLE_CLOUD_PROJECT."
            )
        return resolved_project

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

    def create_bucket(
        self,
        bucket_name: str,
        location: str = "US",
        project_id: Optional[str] = None,
    ) -> str:
        """
        Creates a new bucket in GCS.

        Args:
            bucket_name: The name of the bucket to create.
            location: The GCS location for the bucket (default: "US").

        Returns:
            str: The name of the created bucket.
        """
        try:
            resolved_project = self.resolve_project_id(project_id)
            bucket = self.client.create_bucket(
                bucket_name,
                location=location,
                project=resolved_project,
            )
            logger.info(
                f"Bucket {bucket.name} created in {location} for project {resolved_project}."
            )
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

    def list_buckets(
        self,
        prefix: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> List[str]:
        """
        Lists all buckets visible to the current project credentials
        (optionally filtering by bucket-name prefix).

        Args:
            prefix: Optional prefix to filter bucket names.

        Returns:
            List[str]: A list of bucket names.
        """
        try:
            resolved_project = self.resolve_project_id(project_id)
            buckets = self.client.list_buckets(
                prefix=prefix,
                project=resolved_project,
            )
            bucket_names = [bucket.name for bucket in buckets]
            logger.info(
                f"Listed {len(bucket_names)} buckets with prefix '{prefix or ''}' "
                f"for project {resolved_project}."
            )
            return bucket_names
        except GoogleCloudError as e:
            logger.error(f"Error listing buckets with prefix '{prefix or ''}': {e}")
            raise


def build_gcs_credentials(
    *,
    access_token: Optional[str] = None,
    scopes: Optional[Sequence[str]] = None,
    validate: bool = True,
) -> Credentials:
    """
    Builds Google OAuth2 credentials for GCS from a delegated access token.
    Args:
        access_token: Optional OAuth2 access token.
        validate: Whether to validate token validity before creating credentials.
    Return: A Google Credentials object.
    """

    scopes = list(scopes or GCS_API_CONFIG.read_write_scopes)

    if access_token:
        if validate:
            validate_access_token(access_token, scopes)
        return Credentials(token=access_token, scopes=scopes)

    raise RuntimeError(
        "No GCS credentials available. Provide a delegated user access token header."
    )


def validate_access_token(
    access_token: str, required_scopes: Optional[Sequence[str]] = None
) -> dict[str, Any]:
    """
    Validates an OAuth access token against Google's tokeninfo endpoint.
    Args:
        access_token: The OAuth2 access token to validate.
    Return: The token info payload when token is valid.
    """
    try:
        with httpx.Client() as client:
            response = client.get(
                GCS_AUTH_CONFIG.google_token_info_url_v3,
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
        token_scopes = _expand_storage_scopes(token_scopes)
        missing = [scope for scope in required_scopes if scope not in token_scopes]
        if missing:
            raise AuthenticationError(
                f"Token is missing required scopes: {', '.join(missing)}"
            )

    return token_info


def _expand_storage_scopes(token_scopes: set[str]) -> set[str]:
    """Expands broader Google Cloud / Storage scopes into compatible GCS equivalents."""

    expanded_scopes = set(token_scopes)

    if GCS_API_CONFIG.cloud_platform_scope in expanded_scopes:
        expanded_scopes.update(
            {
                GCS_API_CONFIG.storage_read_only_scope,
                GCS_API_CONFIG.storage_read_write_scope,
                GCS_API_CONFIG.storage_full_control_scope,
            }
        )

    if GCS_API_CONFIG.storage_full_control_scope in expanded_scopes:
        expanded_scopes.update(
            {
                GCS_API_CONFIG.storage_read_only_scope,
                GCS_API_CONFIG.storage_read_write_scope,
            }
        )

    if GCS_API_CONFIG.storage_read_write_scope in expanded_scopes:
        expanded_scopes.add(GCS_API_CONFIG.storage_read_only_scope)

    return expanded_scopes
