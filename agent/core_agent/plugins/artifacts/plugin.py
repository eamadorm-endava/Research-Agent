import copy
import hashlib
from typing import Optional

from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin
from google.genai import types
from loguru import logger


class DeduplicatingArtifactPlugin(SaveFilesAsArtifactsPlugin):
    """Prevents duplicate artifact versions when Gemini Enterprise re-sends files on every turn.

    In production, Gemini Enterprise includes file attachments as inline_data on every turn
    to maintain conversation context. The base plugin calls save_artifact unconditionally,
    creating a new GCS version each time. This plugin checks existing session artifact keys
    before saving and reuses the latest stored version for already-seen filenames.
    """

    async def on_user_message_callback(
        self,
        *,
        invocation_context: InvocationContext,
        user_message: types.Content,
    ) -> Optional[types.Content]:
        """Saves new file attachments and skips re-saves for files already stored in this session.

        Args:
            invocation_context: InvocationContext -> ADK runtime context providing artifact service access.
            user_message: types.Content -> The incoming user message to process.

        Returns:
            Optional[types.Content] -> Modified content with placeholders replacing inline_data, or None if unmodified.
        """
        if not invocation_context.artifact_service:
            logger.warning(
                "Artifact service not configured. DeduplicatingArtifactPlugin is disabled."
            )
            return user_message

        if not user_message.parts:
            return None

        try:
            existing_keys = set(
                await invocation_context.artifact_service.list_artifact_keys(
                    app_name=invocation_context.app_name,
                    user_id=invocation_context.user_id,
                    session_id=invocation_context.session.id,
                )
            )
        except Exception as e:
            logger.warning(
                f"Could not list artifact keys, falling back to base plugin: {e}"
            )
            return await super().on_user_message_callback(
                invocation_context=invocation_context,
                user_message=user_message,
            )

        processed_message_parts = []
        has_artifact_modifications = False

        for message_part in user_message.parts:
            if message_part.inline_data is None:
                processed_message_parts.append(message_part)
                continue

            inline_data = message_part.inline_data
            file_name = inline_data.display_name or self._stable_name_from_content(
                inline_data.data, inline_data.mime_type
            )
            display_name = file_name

            if file_name in existing_keys:
                logger.debug(
                    f"Artifact '{file_name}' already in session — skipping duplicate save."
                )
                version = await self._get_latest_version(
                    invocation_context=invocation_context,
                    file_name=file_name,
                )
            else:
                try:
                    version = await invocation_context.artifact_service.save_artifact(
                        app_name=invocation_context.app_name,
                        user_id=invocation_context.user_id,
                        session_id=invocation_context.session.id,
                        filename=file_name,
                        artifact=copy.copy(message_part),
                    )
                    logger.info(
                        f"Saved new artifact '{file_name}' at version {version}."
                    )
                except Exception as e:
                    logger.error(f"Failed to save artifact '{file_name}': {e}")
                    processed_message_parts.append(message_part)
                    continue

            processed_message_parts.append(
                types.Part(text=f'[Uploaded Artifact: "{display_name}"]')
            )

            file_part = await self._build_file_reference_part(
                invocation_context=invocation_context,
                filename=file_name,
                version=version,
                mime_type=inline_data.mime_type,
                display_name=display_name,
            )
            if file_part:
                processed_message_parts.append(file_part)

            has_artifact_modifications = True

        if has_artifact_modifications:
            return types.Content(role=user_message.role, parts=processed_message_parts)
        return None

    def _stable_name_from_content(
        self, data: Optional[bytes], mime_type: Optional[str]
    ) -> str:
        """Derives a deterministic filename from file bytes when display_name is absent.

        Uses a SHA-256 content hash so the same file always maps to the same key,
        enabling deduplication across turns even when Gemini Enterprise omits display_name.

        Args:
            data: Optional[bytes] -> Raw file bytes.
            mime_type: Optional[str] -> MIME type used to derive the file extension.

        Returns:
            str -> A stable filename of the form artifact_<hex16>.<ext>.
        """
        ext = (mime_type or "application/octet-stream").split("/")[-1]
        digest = hashlib.sha256(data or b"").hexdigest()[:16]
        return f"artifact_{digest}.{ext}"

    async def _get_latest_version(
        self,
        *,
        invocation_context: InvocationContext,
        file_name: str,
    ) -> int:
        """Returns the highest version number stored for an existing artifact.

        Args:
            invocation_context: InvocationContext -> ADK runtime context providing artifact service access.
            file_name: str -> The artifact filename to look up.

        Returns:
            int -> Latest version number; defaults to 0 on error.
        """
        logger.debug(f"Fetching latest version for existing artifact: {file_name}")
        try:
            versions = await invocation_context.artifact_service.list_versions(
                app_name=invocation_context.app_name,
                user_id=invocation_context.user_id,
                filename=file_name,
                session_id=invocation_context.session.id,
            )
            return max(versions) if versions else 0
        except Exception as e:
            logger.warning(
                f"Could not list versions for '{file_name}': {e}. Defaulting to 0."
            )
            return 0
