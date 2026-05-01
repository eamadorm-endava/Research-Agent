import asyncio
import mimetypes
from typing import Optional

from google.adk.artifacts.gcs_artifact_service import GcsArtifactService
from google.genai import types
from loguru import logger
from google.cloud import storage


class StorageService(GcsArtifactService):
    """Refined storage service that uses GCS URI references and IAM conditions.

    In Gemini Enterprise, sending raw bytes in the conversation context is token-expensive.
    This service returns a file_data Part with a gs:// URI, which Gemini can resolve
    natively without bloating the request payload.

    Security is enforced via identity-aware IAM binding conditions at the folder level,
    ensuring users only have access to their own application artifacts.
    """

    async def get_artifact_metadata(
        self,
        app_name: str,
        user_id: str,
        filename: str,
        session_id: Optional[str] = None,
    ) -> Optional[dict[str, str | int]]:
        """Searches GCS for the latest version of an artifact and returns its metadata.

        Args:
            app_name: str -> Name of the application.
            user_id: str -> Identity of the user.
            filename: str -> Name of the file.
            session_id: Optional[str] -> Active session ID.

        Returns:
            Optional[dict[str, str | int]] -> {file_uri, mime_type, size} if found, else None.
        """

        def _lookup() -> Optional[dict[str, str | int]]:
            versions = self._list_versions(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename,
            )
            if not versions:
                return None

            version = max(versions)
            blob_name = self._get_blob_name(
                app_name, user_id, filename, version, session_id
            )
            blob = self.bucket.get_blob(blob_name)
            if not blob:
                return None

            mime_type = blob.content_type
            if not mime_type or mime_type == "application/octet-stream":
                guessed, _ = mimetypes.guess_type(filename)
                mime_type = guessed or "application/pdf"

            return {
                "file_uri": f"gs://{self.bucket.name}/{blob_name}",
                "mime_type": mime_type,
                "size": blob.size,
            }

        return await asyncio.to_thread(_lookup)

    def _load_artifact(
        self,
        app_name: str,
        user_id: str,
        session_id: Optional[str],
        filename: str,
        version: Optional[int] = None,
    ) -> Optional[types.Part]:
        """Returns a file_data reference Part pointing to the GCS object.

        Args:
            app_name: str -> Name of the application.
            user_id: str -> Identity of the user.
            session_id: Optional[str] -> Active session ID.
            filename: str -> Name of the file.
            version: Optional[int] -> Specific version to load.

        Returns:
            Optional[types.Part] -> A file_data Part with the gs:// URI, or None if not found.
        """
        try:
            if version is None:
                versions = self._list_versions(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename,
                )
                if not versions:
                    return None
                version = max(versions)

            blob_name = self._get_blob_name(
                app_name, user_id, filename, version, session_id
            )
            blob = self.bucket.blob(blob_name)

            # We verify the blob exists but don't download it
            if not blob.exists():
                logger.warning(f"Artifact blob not found: {blob_name}")
                return None

            file_uri = f"gs://{self.bucket.name}/{blob_name}"
            logger.debug(f"Resolved artifact reference for agent: {file_uri}")

            # Gemini does not support 'application/octet-stream'. We must provide a valid type.
            res_mime_type = blob.content_type
            if not res_mime_type or res_mime_type == "application/octet-stream":
                guessed, _ = mimetypes.guess_type(filename)
                res_mime_type = guessed or "application/pdf"

            return types.Part(
                file_data=types.FileData(
                    file_uri=file_uri,
                    mime_type=res_mime_type,
                )
            )
        except Exception as error:
            logger.error(f"Failed to load artifact reference for '{filename}': {error}")
            return None

    async def load_artifact_as_bytes(
        self,
        app_name: str,
        user_id: str,
        session_id: Optional[str],
        filename: str,
        version: Optional[int] = None,
    ) -> Optional[types.Part]:
        """Downloads the artifact and returns it as an inline binary Part.

        Use this ONLY when bytes are strictly required (e.g., for Gemini Enterprise
        visual rendering in the final response).

        Args:
            app_name: str -> Name of the application.
            user_id: str -> Identity of the user.
            session_id: Optional[str] -> Active session ID.
            filename: str -> Name of the file.
            version: Optional[int] -> Specific version to load.

        Returns:
            Optional[types.Part] -> An inline_data Part with the bytes, or None if not found.
        """
        try:
            if version is None:
                versions = self._list_versions(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename,
                )
                if not versions:
                    return None
                version = max(versions)

            blob_name = self._get_blob_name(
                app_name, user_id, filename, version, session_id
            )
            blob = self.bucket.blob(blob_name)

            # Standard ADK GcsArtifactService logic but forced to bytes
            artifact_bytes = blob.download_as_bytes()
            if not artifact_bytes:
                return None

            logger.debug(
                f"Downloaded artifact bytes for rendering: {filename} ({len(artifact_bytes)} bytes)"
            )
            return types.Part.from_bytes(
                data=artifact_bytes, mime_type=blob.content_type
            )
        except Exception as error:
            logger.error(f"Failed to load artifact bytes for '{filename}': {error}")
            return None

    async def save_artifact(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        filename: str,
        artifact: types.Part,
    ) -> int:
        """Saves the artifact to GCS and secures it with an IAM binding.

        Args:
            app_name: str -> Name of the application.
            user_id: str -> Identity of the user (email).
            session_id: str -> Active session ID.
            filename: str -> Name of the file.
            artifact: types.Part -> Content to save.

        Returns:
            int -> The version number of the saved artifact.
        """
        # Call the parent save_artifact to perform the actual GCS write
        version = await super().save_artifact(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            artifact=artifact,
        )

        # Secure the file and stamp metadata
        blob_name = self._get_blob_name(
            app_name, user_id, filename, version, session_id
        )
        canonical_uri = f"gs://{self.bucket.name}/{blob_name}"

        logger.info(f"Automatically securing newly saved artifact: {canonical_uri}")
        await self.ensure_uploader_permissions(canonical_uri, user_id, app_name)

        return version

    async def ensure_uploader_permissions(
        self, canonical_uri: str, user_email: str, app_name: Optional[str] = None
    ) -> None:
        """Ensures roles/storage.objectAdmin is granted to the uploader via an IAM binding condition.

        Optimizes permissions by using a folder-level 'startsWith' condition instead of
        per-object bindings.

        Args:
            canonical_uri: str -> The canonical gs:// URI of the uploaded GCS object.
            user_email: str -> The email of the user who performed the upload.
            app_name: Optional[str] -> The app name used to build the folder prefix.
        """
        try:
            object_path = canonical_uri[len("gs://") :]
            bucket_name, object_name = object_path.split("/", 1)
            bucket = (
                self.bucket
                if bucket_name == self.bucket.name
                else storage.Client().bucket(bucket_name)
            )

            # Determine the folder prefix for the user (e.g. core_agent/user@email.com/)
            # If app_name is not provided, we fall back to the parent folder of the object
            folder_prefix = (
                f"{app_name}/{user_email}/"
                if app_name
                else object_name.rsplit("/", 2)[0] + "/"
            )

            def _apply_updates() -> None:
                blob = bucket.get_blob(object_name)
                if not blob:
                    raise ValueError(
                        f"Blob not found for permission/metadata grant: {canonical_uri}"
                    )
                self._grant_iam_conditional_binding(
                    bucket, bucket_name, folder_prefix, user_email
                )
                self._stamp_uploader_metadata(blob, user_email)

            await asyncio.to_thread(_apply_updates)
            logger.info(
                f"Successfully secured folder '{folder_prefix}' and artifact '{canonical_uri}' for: {user_email}"
            )
        except Exception as error:
            logger.warning(
                f"Could not secure artifact '{canonical_uri}' for '{user_email}': {error}"
            )

    def _grant_iam_conditional_binding(
        self,
        bucket: storage.Bucket,
        bucket_name: str,
        folder_prefix: str,
        user_email: str,
    ) -> None:
        """Adds a conditional IAM binding granting roles/storage.objectAdmin on a specific user folder."""
        resource_prefix = f"projects/_/buckets/{bucket_name}/objects/{folder_prefix}"
        condition_expr = f'resource.name.startsWith("{resource_prefix}")'
        iam_policy = bucket.get_iam_policy(requested_policy_version=3)
        iam_policy.version = 3

        already_granted = any(
            binding.get("role") == "roles/storage.objectAdmin"
            and f"user:{user_email}" in binding.get("members", set())
            and (binding.get("condition") or {}).get("expression") == condition_expr
            for binding in iam_policy.bindings
        )

        if already_granted:
            logger.debug(
                f"Folder-level IAM binding already exists for '{user_email}' on '{resource_prefix}'"
            )
            return

        iam_policy.bindings.append(
            {
                "role": "roles/storage.objectAdmin",
                "members": {f"user:{user_email}"},
                "condition": {
                    "title": "uploader-folder-access",
                    "expression": condition_expr,
                },
            }
        )
        bucket.set_iam_policy(iam_policy)
        logger.info(
            f"Granted folder-level roles/storage.objectAdmin to '{user_email}' on '{resource_prefix}'"
        )

    def _stamp_uploader_metadata(self, blob: storage.Blob, user_email: str) -> None:
        """Records the uploader's email in the blob's custom metadata."""
        new_metadata = dict(blob.metadata or {})
        new_metadata["uploader"] = user_email
        blob.metadata = new_metadata
        blob.patch()
