import asyncio
from typing import Optional

from google.adk.artifacts.gcs_artifact_service import GcsArtifactService
from google.genai import types
from loguru import logger
from google.cloud import storage


class GeminiEnterpriseGcsArtifactService(GcsArtifactService):
    """Overrides GcsArtifactService to return GCS URI references instead of binary bytes.

    In Gemini Enterprise, sending raw bytes in the conversation context is token-expensive.
    This service returns a file_data Part with a gs:// URI, which Gemini can resolve
    natively without bloating the request payload.

    For visual rendering in the UI (which requires bytes), use the dedicated
    'load_artifact_as_bytes' method instead.
    """

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

            return types.Part(
                file_data=types.FileData(
                    file_uri=file_uri,
                    mime_type=blob.content_type or "application/octet-stream",
                )
            )
        except Exception as exc:
            logger.error(f"Failed to load artifact reference for '{filename}': {exc}")
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
        except Exception as exc:
            logger.error(f"Failed to load artifact bytes for '{filename}': {exc}")
            return None

    async def save_artifact(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        filename: str,
        artifact: types.Part,
    ) -> int:
        """Saves the artifact to GCS and automatically grants Object Admin ACL to the user.

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

        # Grant ACL and stamp metadata
        blob_name = self._get_blob_name(
            app_name, user_id, filename, version, session_id
        )
        canonical_uri = f"gs://{self.bucket.name}/{blob_name}"

        logger.info(
            f"Automatically granting ACLs on newly saved artifact: {canonical_uri}"
        )
        await self.grant_uploader_object_acl(canonical_uri, user_id)

        return version

    async def grant_uploader_object_acl(
        self, canonical_uri: str, user_email: str
    ) -> None:
        """Grants roles/storage.objectAdmin to the uploader on their GCS object via IAM.

        Args:
            canonical_uri: str -> The canonical gs:// URI of the uploaded GCS object.
            user_email: str -> The email of the user who performed the upload.
        """
        try:
            object_path = canonical_uri[len("gs://") :]
            bucket_name, object_name = object_path.split("/", 1)
            bucket = (
                self.bucket
                if bucket_name == self.bucket.name
                else storage.Client().bucket(bucket_name)
            )

            def _apply_updates() -> None:
                blob = bucket.get_blob(object_name)
                if not blob:
                    raise ValueError(
                        f"Blob not found for ACL/Metadata grant: {canonical_uri}"
                    )
                self._grant_iam_conditional_binding(
                    bucket, bucket_name, object_name, user_email
                )
                self._stamp_uploader_metadata(blob, user_email)

            await asyncio.to_thread(_apply_updates)
            logger.info(
                f"Successfully secured artifact '{canonical_uri}' for: {user_email}"
            )
        except Exception as exc:
            logger.warning(
                f"Could not secure artifact '{canonical_uri}' for '{user_email}': {exc}"
            )

    def _grant_iam_conditional_binding(
        self,
        bucket: storage.Bucket,
        bucket_name: str,
        object_name: str,
        user_email: str,
    ) -> None:
        """Adds a conditional IAM binding granting roles/storage.objectAdmin on a specific object."""
        resource_name = f"projects/_/buckets/{bucket_name}/objects/{object_name}"
        condition_expr = f'resource.name == "{resource_name}"'
        policy = bucket.get_iam_policy(requested_policy_version=3)
        policy.version = 3

        already_granted = any(
            b.get("role") == "roles/storage.objectAdmin"
            and f"user:{user_email}" in b.get("members", set())
            and (b.get("condition") or {}).get("expression") == condition_expr
            for b in policy.bindings
        )

        if already_granted:
            return

        policy.bindings.append(
            {
                "role": "roles/storage.objectAdmin",
                "members": {f"user:{user_email}"},
                "condition": {
                    "title": "uploader-object-access",
                    "expression": condition_expr,
                },
            }
        )
        bucket.set_iam_policy(policy)

    def _stamp_uploader_metadata(self, blob: storage.Blob, user_email: str) -> None:
        """Records the uploader's email in the blob's custom metadata."""
        new_metadata = dict(blob.metadata or {})
        new_metadata["uploader"] = user_email
        blob.metadata = new_metadata
        blob.patch()
