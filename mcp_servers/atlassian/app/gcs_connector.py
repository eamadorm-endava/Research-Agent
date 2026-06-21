import datetime
from typing import Any
from google.cloud import storage
from loguru import logger

from .config import ATLASSIAN_SERVER_CONFIG


class GCSConnector:
    """Handles zero-copy file streaming to the GCS Landing Zone."""

    def __init__(self):
        try:
            self.client = storage.Client()
            self.bucket_name = ATLASSIAN_SERVER_CONFIG.landing_zone_bucket
            if self.bucket_name:
                self.bucket = self.client.bucket(self.bucket_name)
                logger.info(
                    f"GCSConnector initialized successfully for bucket {self.bucket_name}."
                )
            else:
                self.bucket = None
                logger.warning(
                    "GCSConnector initialized without LANDING_ZONE_BUCKET. Ingestion will be unavailable."
                )
        except Exception as e:
            logger.error(f"Failed to initialize GCSConnector: {e}")
            raise

    def upload_stream(
        self,
        file_obj: Any,
        content_type: str,
        app_name: str,
        user_id: str,
        session_id: str,
        filename: str,
        size: int = None,
    ) -> str:
        """Uploads a file-like object directly to the Landing Zone bucket and sets IAM

        so that the file can be safely ingested into the AI Agent's context.

        Args:
            file_obj: Any -> A file-like object containing the data stream
            content_type: str -> The MIME type of the file
            app_name: str -> The name of the calling application or agent
            user_id: str -> The unique identifier of the user
            session_id: str -> The current session or conversation ID
            filename: str -> The name of the file to be uploaded
            size: int -> The explicit size of the file to bypass unseekable
              stream errors

        Returns:
            str -> The canonical GCS URI of the uploaded object
        """
        if not self.bucket:
            raise RuntimeError(
                "Cannot upload to GCS Landing Zone: No bucket name configured."
            )

        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        )
        data_source = "atlassian"

        # gs://{LANDING_ZONE_BUCKET}/<app_name>/<user_id>/<session_id>/<data_source>-<timestamp>-<filename>
        object_name = (
            f"{app_name}/{user_id}/{session_id}/{data_source}-{timestamp}-{filename}"
        )

        try:
            blob = self.bucket.blob(object_name)

            logger.info(
                f"Starting zero-copy stream upload to gs://{self.bucket_name}/{object_name}"
            )
            if size is not None:
                blob.upload_from_file(
                    file_obj, content_type=content_type, size=size, rewind=False
                )
            else:
                blob.upload_from_file(file_obj, content_type=content_type, rewind=False)
            logger.info(
                f"Successfully uploaded object to gs://{self.bucket_name}/{object_name}"
            )

            # Dynamic Authorization: Grant the user read access to their namespace folder
            self._grant_user_access(app_name, user_id)

            return f"gs://{self.bucket_name}/{object_name}"

        except Exception as e:
            logger.error(f"Error uploading to Landing Zone: {e}")
            raise

    def _grant_user_access(self, app_name: str, user_id: str) -> None:
        """Injects an IAM condition into the bucket's IAM policy granting read access

        to the specific user namespace. This guarantees isolation between users.

        Args:
            app_name: str -> The name of the calling application or agent
            user_id: str -> The unique identifier of the user

        Returns:
            None -> Mutates the GCS IAM policy in place
        """
        try:
            resource_prefix = (
                f"projects/_/buckets/{self.bucket_name}/objects/{app_name}/{user_id}/"
            )
            condition_expr = f'resource.name.startsWith("{resource_prefix}")'

            iam_policy = self.bucket.get_iam_policy(requested_policy_version=3)
            iam_policy.version = 3

            member = f"user:{user_id}"

            already_granted = any(
                binding.get("role") == "roles/storage.objectAdmin"
                and member in binding.get("members", set())
                and (binding.get("condition") or {}).get("expression") == condition_expr
                for binding in iam_policy.bindings
            )

            if already_granted:
                logger.debug(
                    f"Folder-level IAM binding already exists for '{member}' on '{resource_prefix}'"
                )
                return

            iam_policy.bindings.append(
                {
                    "role": "roles/storage.objectAdmin",
                    "members": {member},
                    "condition": {
                        "title": "uploader-folder-access",
                        "description": f"Auto-generated by Atlassian MCP Server for user {user_id}",
                        "expression": condition_expr,
                    },
                }
            )
            self.bucket.set_iam_policy(iam_policy)
            logger.info(
                f"Granted roles/storage.objectAdmin to '{member}' for prefix '{resource_prefix}'"
            )

        except Exception as e:
            logger.warning(
                f"Error granting folder IAM condition on {self.bucket_name}: {e}. "
                "This is expected if organizational policies restrict external IAM bindings. "
                "Proceeding as the file upload itself succeeded."
            )
