import asyncio
import copy
from typing import Optional

from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.base_plugin import BasePlugin
from google.cloud import storage
from google.genai import types
from loguru import logger


class GeminiEnterpriseFileIngestionPlugin(BasePlugin):
    """Saves inline files from Gemini Enterprise user messages to GCS.

    Gemini Enterprise sends user-uploaded files as inline types.Part objects
    in the user message. Without this plugin those files are never persisted
    to the agent's GCS bucket. This plugin intercepts each message, saves
    every inline-data part to the configured GcsArtifactService, and replaces
    the binary payload with a text placeholder and a GCS-backed file_data
    reference so the agent can reference the file by URI.
    """

    def __init__(self) -> None:
        super().__init__(name="ge_file_ingestion_plugin")

    async def on_user_message_callback(
        self,
        *,
        invocation_context: InvocationContext,
        user_message: types.Content,
    ) -> Optional[types.Content]:
        """Intercepts the user message, persists any inline files to GCS, and replaces binary payloads with GCS URI references.

        Args:
            invocation_context: InvocationContext -> Full invocation context with artifact service access.
            user_message: types.Content -> Incoming user message that may contain inline file parts.

        Returns:
            Optional[types.Content] -> Modified content with GCS references, or None to proceed unmodified.
        """
        if not invocation_context.artifact_service:
            logger.warning(
                "No artifact service available; GE file ingestion is disabled."
            )
            return None

        if not user_message.parts:
            return None

        new_parts, modified = await self._process_message_parts(
            invocation_context, user_message.parts
        )

        if not modified:
            return None

        return types.Content(role=user_message.role, parts=new_parts)

    async def _process_message_parts(
        self,
        invocation_context: InvocationContext,
        parts: list[types.Part],
    ) -> tuple[list[types.Part], bool]:
        """Iterates over message parts, persisting inline files and replacing them with GCS references.

        Args:
            invocation_context: InvocationContext -> Context with artifact service.
            parts: list[types.Part] -> Original message parts.

        Returns:
            tuple[list[types.Part], bool] -> (processed parts, whether any part was modified).
        """
        new_parts = []
        modified = False

        for index, part in enumerate(parts):
            if part.inline_data is None:
                new_parts.append(part)
                continue

            new_parts.extend(
                await self._process_file_part(invocation_context, part, index)
            )
            modified = True

        return new_parts, modified

    async def _process_file_part(
        self,
        invocation_context: InvocationContext,
        part: types.Part,
        part_index: int,
    ) -> list[types.Part]:
        """Saves a single inline file part to GCS and returns its replacement parts.

        Falls back to the original part on error to avoid data loss.

        Args:
            invocation_context: InvocationContext -> Context with artifact service.
            part: types.Part -> The inline file part to persist.
            part_index: int -> Position in the message, used when generating a fallback filename.

        Returns:
            list[types.Part] -> Replacement parts: a text placeholder and optionally a GCS file_data reference.
        """
        try:
            inline_data = part.inline_data
            filename = (
                inline_data.display_name
                or f"upload_{invocation_context.invocation_id}_{part_index}"
            )
            logger.info(f"Persisting GE user upload to artifact store: {filename}")

            version = await invocation_context.artifact_service.save_artifact(
                app_name=invocation_context.app_name,
                user_id=invocation_context.user_id,
                session_id=invocation_context.session.id,
                filename=filename,
                artifact=copy.copy(part),
            )

            result = [types.Part(text=f'[Uploaded Artifact: "{filename}"]')]
            gcs_part = await self._build_gcs_reference_part(
                invocation_context, filename, version, inline_data.mime_type
            )
            if gcs_part:
                result.append(gcs_part)
                await self._grant_uploader_object_acl(
                    gcs_part.file_data.file_uri, invocation_context.user_id
                )
            return result

        except Exception as exc:
            logger.error(f"Failed to persist user upload (part {part_index}): {exc}")
            return [part]

    async def _build_gcs_reference_part(
        self,
        invocation_context: InvocationContext,
        filename: str,
        version: int,
        mime_type: Optional[str],
    ) -> Optional[types.Part]:
        """Retrieves the canonical GCS URI for a saved artifact and wraps it in a file_data Part.

        Args:
            invocation_context: InvocationContext -> Context with artifact service.
            filename: str -> The saved artifact filename.
            version: int -> The version returned by save_artifact.
            mime_type: Optional[str] -> MIME type of the file.

        Returns:
            Optional[types.Part] -> A file_data Part with the gs:// URI, or None if unavailable.
        """
        try:
            artifact_version = (
                await invocation_context.artifact_service.get_artifact_version(
                    app_name=invocation_context.app_name,
                    user_id=invocation_context.user_id,
                    session_id=invocation_context.session.id,
                    filename=filename,
                    version=version,
                )
            )
        except Exception as exc:
            logger.warning(f"Could not retrieve GCS URI for '{filename}': {exc}")
            return None

        if not artifact_version or not artifact_version.canonical_uri:
            logger.debug(f"No canonical URI available for artifact: {filename}")
            return None

        if not artifact_version.canonical_uri.startswith("gs://"):
            logger.debug(
                f"Non-GCS URI skipped for agent reference: {artifact_version.canonical_uri}"
            )
            return None

        logger.debug(
            f"GCS URI resolved for '{filename}': {artifact_version.canonical_uri}"
        )
        return types.Part(
            file_data=types.FileData(
                file_uri=artifact_version.canonical_uri,
                mime_type=mime_type or artifact_version.mime_type,
                display_name=filename,
            )
        )

    async def _grant_uploader_object_acl(
        self, canonical_uri: str, user_email: str
    ) -> None:
        """Grants the uploading user OWNER-level ACL on their uploaded GCS object.

        Uses Application Default Credentials (service account) to set per-object ACL,
        giving the uploader storage.objectAdmin access over the specific file they uploaded.
        Logs a warning without raising if the grant fails (e.g., uniform bucket-level access).

        Args:
            canonical_uri: str -> The canonical gs:// URI of the uploaded GCS object.
            user_email: str -> The email of the user who performed the upload.

        Returns:
            None
        """
        try:
            object_path = canonical_uri[len("gs://") :]
            bucket_name, object_name = object_path.split("/", 1)
            client = storage.Client()
            blob = client.bucket(bucket_name).blob(object_name)

            def _apply_acl() -> None:
                blob.acl.reload()
                blob.acl.user(user_email).grant_owner()
                blob.acl.save()

            await asyncio.to_thread(_apply_acl)
            logger.info(
                f"Granted OWNER ACL on '{canonical_uri}' for uploader: {user_email}"
            )
        except Exception as exc:
            logger.warning(
                f"Could not set uploader ACL on '{canonical_uri}' for '{user_email}': {exc}"
            )
