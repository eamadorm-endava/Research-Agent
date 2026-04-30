import copy
import mimetypes
import re
from typing import Optional

from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.base_plugin import BasePlugin
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
        """Intercepts the user message, persists any inline files to GCS, replaces binary payloads
        with GCS URI references, and secures GCS file_data references pre-uploaded by GE.

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
            logger.debug("User message has no parts; skipping GE file ingestion.")
            return None

        logger.info(
            f"GeminiEnterpriseFileIngestionPlugin: Intercepted message with {len(user_message.parts)} part(s) from user: {invocation_context.user_id}"
        )
        for part_index, part in enumerate(user_message.parts):
            self._log_part_summary(part_index, part)

        # Local turn-based registry for linking filenames to GCS URIs and metadata
        # Structure: { "filename": { "file_uri": "gs://...", "mime_type": "..." } }
        turn_registry: dict[str, dict[str, str]] = {}

        # 1. Secure any GCS references already present in the message (pre-uploaded by GE)
        await self._secure_gcs_file_references(
            invocation_context, user_message.parts, turn_registry
        )

        # 2. Process inline binary data, saving it to GCS and replacing with references
        message_parts, modified_inline = await self._process_message_parts(
            invocation_context, user_message.parts, turn_registry
        )

        # 3. Process GE text-extracted blocks (tags in text parts)
        new_parts, modified_text = await self._process_ge_text_blocks(
            invocation_context, message_parts, turn_registry
        )

        if not (modified_inline or modified_text):
            logger.debug(
                "No inline data or GE text blocks found; message left unmodified."
            )
            return None

        logger.info(
            f"Plugin modified message: inline={modified_inline}, text_blocks={modified_text}. Final summary of parts sent to agent:"
        )
        for part_index, part in enumerate(new_parts):
            self._log_part_summary(part_index, part)

        return types.Content(role=user_message.role, parts=new_parts)

    async def _process_message_parts(
        self,
        invocation_context: InvocationContext,
        parts: list[types.Part],
        turn_registry: dict[str, dict[str, str]],
    ) -> tuple[list[types.Part], bool]:
        """Iterates over message parts, persisting inline files and replacing them with GCS references.

        Args:
            invocation_context: InvocationContext -> Context with artifact service.
            parts: list[types.Part] -> Original message parts.
            turn_registry: dict[str, dict[str, str]] -> Local registry to populate.

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
                await self._process_file_part(
                    invocation_context, part, index, turn_registry
                )
            )
            modified = True

        return new_parts, modified

    async def _process_ge_text_blocks(
        self,
        invocation_context: InvocationContext,
        parts: list[types.Part],
        turn_registry: dict[str, dict[str, str]],
    ) -> tuple[list[types.Part], bool]:
        """Scans text parts for GE file delimiters, persists content to GCS, and replaces tags.

        Handles cases where tags and content may be split across multiple consecutive text parts.

        Args:
            invocation_context: InvocationContext -> Context with artifact service.
            parts: list[types.Part] -> Current message parts.
            turn_registry: dict[str, dict[str, str]] -> Local registry to use for resolution.

        Returns:
            tuple[list[types.Part], bool] -> (processed parts, whether any text blocks were modified).
        """
        # Regex to find: <start_of_user_uploaded_file: filename> ... <end_of_user_uploaded_file: filename>
        # Handles optional newlines and spaces.
        ge_tag_pattern = re.compile(
            r"\n?<start_of_user_uploaded_file:\s*(.*?)\s*>\n?(.*?)\n?<end_of_user_uploaded_file:\s*\1\s*>\n?",
            re.DOTALL,
        )

        new_parts = []
        modified = False
        i = 0
        while i < len(parts):
            # Identify a sequence of consecutive text parts
            if getattr(parts[i], "text", None) is None:
                new_parts.append(parts[i])
                i += 1
                continue

            text_sequence = []
            start_idx = i
            while i < len(parts) and getattr(parts[i], "text", None) is not None:
                text_sequence.append(parts[i].text)
                i += 1

            full_text = "".join(text_sequence)
            matches = list(ge_tag_pattern.finditer(full_text))

            if not matches:
                # No blocks in this sequence; restore the original parts
                new_parts.extend(parts[start_idx:i])
                continue

            # Process matches and replace in text
            modified = True
            last_end = 0
            for match in matches:
                # Keep text before the match
                prefix = full_text[last_end : match.start()]
                if prefix:
                    new_parts.append(types.Part(text=prefix))

                filename = match.group(1)
                content = match.group(2)

                # Save the extracted text as a .txt artifact (or resolve from registry)
                replacement_parts = await self._process_ge_text_match(
                    invocation_context, filename, content, match.group(0), turn_registry
                )
                new_parts.extend(replacement_parts)
                last_end = match.end()

            # Keep text after the last match
            suffix = full_text[last_end:]
            if suffix:
                new_parts.append(types.Part(text=suffix))

        return new_parts, modified

    async def _process_ge_text_match(
        self,
        invocation_context: InvocationContext,
        filename: str,
        content: str,
        original_text: str,
        turn_registry: dict[str, dict[str, str]],
    ) -> list[types.Part]:
        """Saves a single GE text block as a .txt artifact (or resolves it from storage)
        and returns replacement parts.

        Args:
            invocation_context: InvocationContext -> Context with artifact service.
            filename: str -> Original filename from the tag.
            content: str -> Extracted text content.
            original_text: str -> The raw text of the match, used as a fallback on failure.
            turn_registry: dict[str, dict[str, str]] -> Local registry for cross-part resolution.

        Returns:
            list[types.Part] -> Replacement parts: text placeholder and GCS reference.
        """
        # 1. Check turn registry (populated by binary/GCS parts in this turn)
        if filename in turn_registry:
            metadata = turn_registry[filename]
            logger.info(f"Resolved GE text tag '{filename}' from turn registry.")
            return [
                types.Part(text=f'[Uploaded Artifact: "{filename}"]'),
                types.Part(
                    file_data=types.FileData(
                        file_uri=metadata["file_uri"],
                        mime_type=metadata["mime_type"],
                    )
                ),
            ]

        # 2. Check GCS (Lazy Association for pre-stashed files)
        storage_service = invocation_context.artifact_service
        metadata = await storage_service.get_artifact_metadata(
            app_name=invocation_context.app_name,
            user_id=invocation_context.user_id,
            filename=filename,
            session_id=invocation_context.session.id,
        )

        if metadata:
            logger.info(f"Resolved GE text tag '{filename}' via GCS discovery.")
            # Ensure security is active for the discovered URI
            await storage_service.ensure_uploader_permissions(
                metadata["file_uri"],
                invocation_context.user_id,
                invocation_context.app_name,
            )
            return [
                types.Part(text=f'[Uploaded Artifact: "{filename}"]'),
                types.Part(
                    file_data=types.FileData(
                        file_uri=metadata["file_uri"],
                        mime_type=metadata["mime_type"],
                    )
                ),
            ]

        # 3. Guard for empty content if not found in GCS/Registry
        if not content or not content.strip():
            logger.warning(
                f"Extracted content for '{filename}' is empty and not found in storage; skipping artifact persistence."
            )
            return [types.Part(text=f'[Empty/Non-text Artifact: "{filename}"]')]

        # 4. Fallback: Persist as .txt if content is present
        txt_filename = f"{filename}.txt"
        logger.info(
            f"Persisting GE text-extracted file to artifact store: {txt_filename}"
        )

        try:
            # Create a text Part for the extracted content
            text_part = types.Part(text=content)

            # save_artifact in StorageService automatically secures the file via IAM
            version = await invocation_context.artifact_service.save_artifact(
                app_name=invocation_context.app_name,
                user_id=invocation_context.user_id,
                session_id=invocation_context.session.id,
                filename=txt_filename,
                artifact=text_part,
            )

            result = [types.Part(text=f'[Uploaded Artifact: "{filename}"]')]
            gcs_part = await self._build_gcs_reference_part(
                invocation_context, txt_filename, version, "text/plain"
            )
            if gcs_part:
                result.append(gcs_part)

            return result

        except Exception as error:
            logger.error(f"Failed to persist GE text block '{filename}': {error}")
            # On failure, return the original text block to avoid data loss
            return [types.Part(text=original_text)]

    async def _process_file_part(
        self,
        invocation_context: InvocationContext,
        part: types.Part,
        part_index: int,
        turn_registry: dict[str, dict[str, str]],
    ) -> list[types.Part]:
        """Saves a single inline file part to GCS and returns its replacement parts.

        Falls back to the original part on error to avoid data loss.

        Args:
            invocation_context: InvocationContext -> Context with artifact service.
            part: types.Part -> The inline file part to persist.
            part_index: int -> Position in the message, used when generating a fallback filename.
            turn_registry: dict[str, dict[str, str]] -> Local registry to populate.

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

            # save_artifact in StorageService automatically grants IAM conditions
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
                # Populate registry for subsequent GE tag resolution
                file_data = getattr(gcs_part, "file_data", None)
                if file_data:
                    turn_registry[filename] = {
                        "file_uri": file_data.file_uri,
                        "mime_type": file_data.mime_type,
                    }

            return result

        except Exception as error:
            logger.error(f"Failed to persist user upload (part {part_index}): {error}")
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
        except Exception as error:
            logger.warning(f"Could not retrieve GCS URI for '{filename}': {error}")
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
        # Gemini does not support 'application/octet-stream'.
        res_mime_type = mime_type or artifact_version.mime_type
        if not res_mime_type or res_mime_type == "application/octet-stream":
            guessed, _ = mimetypes.guess_type(filename)
            res_mime_type = guessed or "application/pdf"

        return types.Part(
            file_data=types.FileData(
                file_uri=artifact_version.canonical_uri,
                mime_type=res_mime_type,
                display_name=filename,
            )
        )

    def _log_part_summary(self, index: int, part: types.Part) -> None:
        """Logs a human-readable summary of a single message part for diagnostics.

        Truncates text to 120 characters, records mime_type and display_name for
        inline_data, and logs the URI for file_data. Binary payloads are never logged.

        Args:
            index: int -> Zero-based position of the part in the message.
            part: types.Part -> The part to summarise.

        Returns:
            None
        """
        logger.debug(f"Part as json: {part.model_dump()}")
        inline = getattr(part, "inline_data", None)
        file_data = getattr(part, "file_data", None)
        text = getattr(part, "text", None)

        if inline is not None:
            data_len = len(inline.data) if inline.data else 0
            logger.info(
                f"  part[{index}] inline_data — mime={inline.mime_type!r} "
                f"display_name={inline.display_name!r} bytes={data_len}"
            )
        elif file_data is not None:
            logger.info(
                f"  part[{index}] file_data  — uri={getattr(file_data, 'file_uri', None)!r} "
                f"mime={getattr(file_data, 'mime_type', None)!r}"
            )
        elif text is not None:
            preview = text[:120].replace("\n", "\\n")
            logger.debug(
                f"  part[{index}] text       — {preview!r}{'…' if len(text) > 120 else ''}"
            )
        else:
            logger.debug(f"  part[{index}] unknown    — {type(part)}")

    async def _secure_gcs_file_references(
        self,
        invocation_context: InvocationContext,
        parts: list[types.Part],
        turn_registry: dict[str, dict[str, str]],
    ) -> None:
        """Secures any GCS file_data references already in the message via IAM.

        Gemini Enterprise may pre-upload larger files directly to GCS and pass them as file_data
        parts. This ensures those objects also receive the correct uploader identity ACLs.

        Args:
            invocation_context: InvocationContext -> Context with session state.
            parts: list[types.Part] -> Message parts to scan for GCS references.
            turn_registry: dict[str, dict[str, str]] -> Local registry to populate with found URIs.
        """
        user_identity = invocation_context.user_id
        if not user_identity:
            logger.warning(
                "No user identity found in context; skipping IAM security grant."
            )
            return

        # We try to use the custom service's permission method if available
        storage_service = invocation_context.artifact_service
        permission_grant_function = getattr(
            storage_service, "ensure_uploader_permissions", None
        )

        if not permission_grant_function:
            logger.debug(
                "Artifact service does not support manual IAM grants; skipping pre-existing files."
            )
            return

        for part in parts:
            file_data = getattr(part, "file_data", None)
            file_uri = getattr(file_data, "file_uri", None) if file_data else None

            if file_uri and file_uri.startswith("gs://"):
                logger.info(
                    f"Found existing GCS reference: {file_uri}. Requesting IAM permission grant for {user_identity}"
                )
                await permission_grant_function(
                    file_uri, user_identity, invocation_context.app_name
                )
                # Populate registry with the found reference (filename is derived from URI)
                filename = file_uri.split("/")[-1]
                turn_registry[filename] = {
                    "file_uri": file_uri,
                    "mime_type": getattr(file_data, "mime_type", "application/pdf"),
                }
