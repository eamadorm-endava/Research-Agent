import re
from typing import Optional

from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types
from loguru import logger


class GeminiEnterpriseFileIngestionPlugin(BasePlugin):
    """Intercepts Gemini Enterprise user messages and resolves uploaded files via GCS.

    Gemini Enterprise (GE) automatically saves user-uploaded files to GCS via the ArtifactService.
    It then injects tags into the user prompt like:
    <start_of_user_uploaded_file: filename> ... <end_of_user_uploaded_file: filename>

    This plugin scans for these tags, looks up the corresponding file in GCS using the filename,
    and replaces the text tags with a proper types.Part(file_data=...) reference so the LLM
    can natively read the file.
    """

    def __init__(self) -> None:
        super().__init__(name="ge_file_ingestion_plugin")

    def _log_message_parts_summary(
        self,
        user_id: str,
        message_parts: list[types.Part],
        prefix: str = "Intercepted message",
    ) -> None:
        """Logs a summary for a collection of message parts.

        Args:
            user_id: str -> The user identity.
            message_parts: list[types.Part] -> The message parts to summarize.
            prefix: str -> A prefix for the log message.

        Returns:
            None -> This function does not return a value.
        """
        logger.info(
            f"GeminiEnterpriseFileIngestionPlugin: {prefix} with {len(message_parts)} part(s) from user: {user_id}"
        )
        for index, part in enumerate(message_parts):
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

    async def on_user_message_callback(
        self,
        *,
        invocation_context: InvocationContext,
        user_message: types.Content,
    ) -> Optional[types.Content]:
        """Intercepts the user message and replaces GE text tags with GCS references.

        Args:
            invocation_context: InvocationContext -> Full invocation context with artifact service access.
            user_message: types.Content -> Incoming user message.

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

        self._log_message_parts_summary(
            invocation_context.user_id or "unknown", user_message.parts
        )

        new_parts, modified = await self._process_ge_text_blocks(
            invocation_context, user_message.parts
        )

        if not modified:
            logger.debug("No GE text blocks found; message left unmodified.")
            return None

        self._log_message_parts_summary(
            invocation_context.user_id or "unknown",
            new_parts,
            f"Plugin modified message: text_blocks={modified}. Final summary of parts sent to agent",
        )

        return types.Content(role=user_message.role, parts=new_parts)

    def _extract_text_sequence(
        self, message_parts: list[types.Part], sequence_start_index: int
    ) -> tuple[int, str]:
        """Extracts a sequence of consecutive text parts starting from a specific index.

        Gemini Enterprise tags might be split across multiple consecutive `types.Part(text=...)`
        objects if the message is large or chunks were created during network transport.
        This method concatenates all consecutive text parts into a single string so our Regex
        doesn't miss tags that are cut in half across two parts.

        Args:
            message_parts: list[types.Part] -> The message parts.
            sequence_start_index: int -> The index to start extracting from.

        Returns:
            tuple[int, str] -> The next index after the sequence and the concatenated text.
        """
        extracted_text_blocks = []
        current_index = sequence_start_index
        while (
            current_index < len(message_parts)
            and getattr(message_parts[current_index], "text", None) is not None
        ):
            extracted_text_blocks.append(message_parts[current_index].text)
            current_index += 1
        return current_index, "".join(extracted_text_blocks)

    async def _replace_matches_in_text(
        self,
        invocation_context: InvocationContext,
        aggregated_text_sequence: str,
        ge_tag_matches: list[re.Match],
    ) -> list[types.Part]:
        """Replaces matched GE file blocks in text with GCS references.

        When GE injects `<start_of_user_uploaded_file: filename>` tags, it creates one giant string
        containing both the user's prompt text AND the uploaded tags. This method iterates through
        the regex matches, extracts the actual user text surrounding the tags, and swaps out the
        GE tags for native `types.Part(file_data=...)` references linked to GCS.

        Args:
            invocation_context: InvocationContext -> Context with artifact service.
            aggregated_text_sequence: str -> The full text sequence containing the user's prompt and GE tags.
            ge_tag_matches: list[re.Match] -> Regex matches of GE tags found in the text.

        Returns:
            list[types.Part] -> Replacement parts containing the user's text and GCS references.
        """
        resolved_message_parts = []
        last_processed_char_index = 0
        for match in ge_tag_matches:
            # 1. Preserve any actual user text that appeared BEFORE the GE tag
            text_before_tag = aggregated_text_sequence[
                last_processed_char_index : match.start()
            ]
            if text_before_tag:
                resolved_message_parts.append(types.Part(text=text_before_tag))

            # 2. Extract the filename from the first capture group of the regex
            filename = match.group(1)

            # 3. Ask the artifact service for the GCS URI associated with this filename
            resolved_gcs_parts = await self._resolve_ge_text_match(
                invocation_context, filename, match.group(0)
            )
            resolved_message_parts.extend(resolved_gcs_parts)

            # Update the pointer so we can process the text after this tag
            last_processed_char_index = match.end()

        # 4. Preserve any actual user text that appeared AFTER the last GE tag
        text_after_last_tag = aggregated_text_sequence[last_processed_char_index:]
        if text_after_last_tag:
            resolved_message_parts.append(types.Part(text=text_after_last_tag))

        return resolved_message_parts

    async def _process_ge_text_blocks(
        self,
        invocation_context: InvocationContext,
        original_message_parts: list[types.Part],
    ) -> tuple[list[types.Part], bool]:
        """Scans text parts for GE file delimiters and replaces tags with GCS references.

        This is the core loop of the plugin. It iterates over the incoming message parts. If it
        finds text, it aggregates it, runs a regex to find `<start_of_user_uploaded_file...>`,
        and replaces those tags with actual GCS file objects. This prevents the LLM from receiving
        meaningless text tags and instead provides it with the actual file.

        Args:
            invocation_context: InvocationContext -> Context with artifact service.
            original_message_parts: list[types.Part] -> Current message parts.

        Returns:
            tuple[list[types.Part], bool] -> Processed parts and whether any text blocks were modified.
        """
        # Regex to find: <start_of_user_uploaded_file: filename> ... <end_of_user_uploaded_file: filename>
        # Handles optional newlines and spaces that GE sometimes injects around the tags.
        ge_uploaded_file_tag_pattern = re.compile(
            r"\n?<start_of_user_uploaded_file:\s*(.*?)\s*>\n?(.*?)\n?<end_of_user_uploaded_file:\s*\1\s*>\n?",
            re.DOTALL,
        )

        processed_message_parts = []
        were_parts_modified = False
        part_index = 0
        while part_index < len(original_message_parts):
            # If it's not a text part (e.g. function_call or binary), ignore it and move on
            if getattr(original_message_parts[part_index], "text", None) is None:
                processed_message_parts.append(original_message_parts[part_index])
                part_index += 1
                continue

            # It's a text part. Extract all consecutive text parts into one big string
            sequence_start_index = part_index
            part_index, aggregated_text_sequence = self._extract_text_sequence(
                original_message_parts, sequence_start_index
            )

            # Find all GE uploaded file tags within this text block
            ge_tag_matches = list(
                ge_uploaded_file_tag_pattern.finditer(aggregated_text_sequence)
            )

            if not ge_tag_matches:
                # No file tags found, just restore the original parts unmodified
                processed_message_parts.extend(
                    original_message_parts[sequence_start_index:part_index]
                )
                continue

            # We found file tags! Replace them with actual GCS references.
            were_parts_modified = True
            resolved_gcs_parts = await self._replace_matches_in_text(
                invocation_context, aggregated_text_sequence, ge_tag_matches
            )
            processed_message_parts.extend(resolved_gcs_parts)

        return processed_message_parts, were_parts_modified

    async def _resolve_ge_text_match(
        self,
        invocation_context: InvocationContext,
        filename: str,
        fallback_text_representation: str,
    ) -> list[types.Part]:
        """Resolves the artifact from GCS via metadata lookup.

        When GE processes an upload, it uses the ADK ArtifactService to push the file to the
        agent's Landing Zone bucket. This method uses that same ArtifactService to fetch the
        file's metadata (including its gs:// URI and mime-type) using just the filename
        provided in the text tag. If found, it dynamically grants IAM permission to the agent
        and returns the GCS reference.

        Args:
            invocation_context: InvocationContext -> Context with artifact service.
            filename: str -> Original filename from the GE tag.
            fallback_text_representation: str -> The raw text of the match, used as a fallback if GCS fails.

        Returns:
            list[types.Part] -> Replacement parts: a UI text placeholder and the actual GCS reference.
        """
        storage_service = invocation_context.artifact_service
        if not invocation_context.user_id:
            logger.debug(
                f"No user identity for discovery of '{filename}'; skipping GCS lookup."
            )
            return [types.Part(text=fallback_text_representation)]

        try:
            metadata = await storage_service.get_artifact_metadata(
                app_name=invocation_context.app_name,
                user_id=invocation_context.user_id,
                filename=filename,
                session_id=invocation_context.session.id,
            )
        except Exception as e:
            logger.error(f"Failed to lookup metadata for '{filename}': {e}")
            return [types.Part(text=fallback_text_representation)]

        if not metadata:
            logger.warning(
                f"Extracted content for '{filename}' not found in storage; skipping."
            )
            return [types.Part(text=f'[Empty/Non-text Artifact: "{filename}"]')]

        logger.info(f"Resolved GE text tag '{filename}' via GCS discovery.")
        await storage_service.ensure_uploader_permissions(
            metadata["file_uri"],
            invocation_context.user_id,
            invocation_context.app_name,
        )
        return [
            types.Part(text=f'[Uploaded Artifact: "{filename}"]'),
            types.Part(
                file_data=types.FileData(
                    file_uri=metadata["file_uri"], mime_type=metadata["mime_type"]
                )
            ),
        ]
