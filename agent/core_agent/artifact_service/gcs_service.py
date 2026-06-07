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

    Unified Ingestion:
    While this class directly handles the saving of local UI uploads and agent-generated
    artifacts, it serves as the global artifact retriever. When external data sources
    (Google Drive, Confluence, etc.) are ingested via MCP Servers, they are uploaded to
    the exact same Landing Zone path. Because the paths are unified, this service can
    natively discover and load those external files just like local artifacts.

    1. User Uploads: Triggered by a user explicitly uploading a file in the Gemini Enterprise UI.
    2. External Generation: If an external system or MCP server fetches a file, the `FileIngestionToolWrapper`
    injects the exact same zero-copy `gs://` URI natively into the conversation history, allowing the agent
    to process the external document instantly within the same turn, avoiding latency and eliminating
    the need for a secondary tool call to fetch the newly uploaded artifact.
    """

    async def get_artifact_metadata(
        self,
        app_name: str,
        user_id: str,
        filename: str,
        session_id: Optional[str] = None,
    ) -> Optional[dict[str, str]]:
        """Searches GCS for the latest version of an artifact and returns its URI and MIME type.

        Args:
            app_name: str -> Name of the application.
            user_id: str -> Identity of the user.
            filename: str -> Name of the file.
            session_id: Optional[str] -> Active session ID.

        Returns:
            Optional[dict[str, str]] -> {file_uri, mime_type} if found, else None.
        """

        def _lookup() -> Optional[dict[str, str]]:
            """Executes the synchronous GCS blob lookup and MIME type resolution.

            Args:
                None -> No arguments.

            Returns:
                Optional[dict[str, str]] -> {file_uri, mime_type} if found, else None.
            """
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
        """Returns a file_data reference Part pointing to the GCS object to be sent in an LLM turn to analyze/read it

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

    async def save_artifact(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        filename: str,
        artifact: types.Part,
    ) -> int:
        """Saves the artifact to GCS and secures it with an IAM binding. Typically called when the user uploads an artifact directly in the UI
        or the model generates one (e.g. a csv).

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
        gcs_uri = f"gs://{self.bucket.name}/{blob_name}"

        logger.info(f"Automatically securing newly saved artifact: {gcs_uri}")
        await self.ensure_uploader_permissions(gcs_uri, user_id, app_name)

        return version

    async def ensure_uploader_permissions(
        self, gcs_uri: str, user_email: str, app_name: Optional[str] = None
    ) -> None:
        """Ensures roles/storage.objectAdmin is granted to the uploader via an IAM binding condition.

        Optimizes permissions by using a folder-level 'startsWith' condition instead of
        per-object bindings.

        Args:
            gcs_uri: str -> The gcs uri of the uploaded GCS object.
            user_email: str -> The email of the user who performed the upload.
            app_name: Optional[str] -> The app name used to build the folder prefix.

        Returns:
            None
        """
        try:
            object_path = gcs_uri[len("gs://") :]
            bucket_name, object_name = object_path.split("/", 1)

            # SECURITY (Broken Access Control / SSRF Guardrail):
            # Prevents malicious API callers or intercepted UI payloads from passing a
            # file_data URI pointing to a foreign bucket, which would otherwise trick
            # the agent into mutating IAM policies on buckets it doesn't own.
            if bucket_name != self.bucket.name:
                logger.warning(
                    f"Security Exception: Cannot secure artifact outside the managed Landing Zone bucket: {gcs_uri}"
                )
                return
            bucket = self.bucket

            # Determine the folder prefix for the user (e.g. core_agent/user@email.com/)
            # If app_name is not provided, we fall back to the parent folder of the object
            folder_prefix = (
                f"{app_name}/{user_email}/"
                if app_name
                else object_name.rsplit("/", 2)[0] + "/"
            )

            def _apply_updates() -> None:
                """Applies the folder-level IAM conditions and stamps uploader metadata.

                Args:
                    None -> No arguments.

                Returns:
                    None -> Modifies the GCS bucket IAM policy and blob metadata.
                """
                blob = bucket.get_blob(object_name)
                if not blob:
                    raise ValueError(
                        f"Blob not found for permission/metadata grant: {gcs_uri}"
                    )
                self._grant_iam_conditional_binding(
                    bucket, bucket_name, folder_prefix, user_email
                )
                self._stamp_uploader_metadata(blob, user_email)

            await asyncio.to_thread(_apply_updates)
            logger.info(
                f"Successfully secured folder '{folder_prefix}' and artifact '{gcs_uri}' for: {user_email}"
            )
        except Exception as error:
            logger.warning(
                f"Could not secure artifact '{gcs_uri}' for '{user_email}': {error}"
            )

    def _grant_iam_conditional_binding(
        self,
        bucket: storage.Bucket,
        bucket_name: str,
        folder_prefix: str,
        user_email: str,
    ) -> None:
        """Adds a conditional IAM binding granting roles/storage.objectAdmin on a specific user folder.

        This enables zero-trust security architecture, where a user can only list/read/write
        artifacts within their designated workspace prefix.

        Args:
            bucket: storage.Bucket -> The GCS Bucket to apply the IAM policy on.
            bucket_name: str -> The string name of the GCS bucket.
            folder_prefix: str -> The specific folder path granting access to the user.
            user_email: str -> The identity of the user.

        Returns:
            None -> Mutates the GCS IAM policy in place.
        """
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
        """Records the uploader's email in the blob's custom metadata.

        This enables auditability so that any file can be traced back to its uploader,
        preventing spoofing and enforcing identity tracking.

        Args:
            blob: storage.Blob -> The GCS Blob object.
            user_email: str -> The identity of the user who uploaded the file.

        Returns:
            None -> Updates the metadata of the GCS object.
        """
        new_metadata = dict(blob.metadata or {})
        new_metadata["uploader"] = user_email
        blob.metadata = new_metadata
        blob.patch()
