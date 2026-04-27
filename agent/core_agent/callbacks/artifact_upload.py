from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types
from loguru import logger

_ARTIFACT_STATE_KEY = "latest_uploaded_artifacts"
_UPLOAD_NOTICE_PREFIX = "Uploaded file saved as ADK artifact"


def _artifact_name_for_part(part: types.Part, index: int) -> str:
    """Builds a stable artifact filename for an uploaded inline-data part."""
    inline_data = getattr(part, "inline_data", None)
    display_name = getattr(inline_data, "display_name", None)
    if display_name and str(display_name).strip():
        return Path(str(display_name)).name

    mime_type = getattr(inline_data, "mime_type", None) or "application/octet-stream"
    extension = mimetypes.guess_extension(mime_type) or ".bin"
    return f"uploaded-artifact-{index}{extension}"


def _iter_user_contents(callback_context: CallbackContext, llm_request: LlmRequest):
    """Yields user content objects that can contain uploaded file parts."""
    user_content = getattr(callback_context, "user_content", None)
    if user_content is not None:
        yield user_content

    for content in reversed(getattr(llm_request, "contents", None) or []):
        if getattr(content, "role", None) == "user":
            yield content
            break


def _replace_inline_file_parts_with_notices(
    content: Any,
    artifact_names_by_index: dict[int, str],
) -> None:
    """Keeps the model request lightweight after uploaded files are persisted."""
    parts = getattr(content, "parts", None)
    if not parts:
        return

    replacement_parts = []
    changed = False
    for index, part in enumerate(parts):
        if index in artifact_names_by_index:
            changed = True
            replacement_parts.append(
                types.Part(
                    text=(
                        f"[{_UPLOAD_NOTICE_PREFIX}: {artifact_names_by_index[index]}]"
                    )
                )
            )
        else:
            replacement_parts.append(part)

    if changed:
        content.parts = replacement_parts


async def persist_uploaded_files_as_artifacts(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """Persists uploaded inline file parts as ADK artifacts before model/tool work.

    This keeps the deployment entrypoint unchanged (`app` remains the Vertex AI
    `AdkApp`) while making uploaded Dev UI / Gemini Enterprise file bytes
    available to tools through `ToolContext.list_artifacts()` and
    `ToolContext.load_artifact()`.
    """
    tracked_names: list[str] = []

    for content in _iter_user_contents(callback_context, llm_request):
        artifact_names_by_index: dict[int, str] = {}
        parts = getattr(content, "parts", None) or []

        for index, part in enumerate(parts):
            inline_data = getattr(part, "inline_data", None)
            if inline_data is None or getattr(inline_data, "data", None) is None:
                continue

            artifact_name = _artifact_name_for_part(part, index)
            await callback_context.save_artifact(artifact_name, part)
            artifact_names_by_index[index] = artifact_name
            if artifact_name not in tracked_names:
                tracked_names.append(artifact_name)

        _replace_inline_file_parts_with_notices(content, artifact_names_by_index)

    if tracked_names:
        existing_names = callback_context.state.get(_ARTIFACT_STATE_KEY) or []
        deduped_names: list[str] = []
        for name in [*existing_names, *tracked_names]:
            if name not in deduped_names:
                deduped_names.append(name)
        callback_context.state[_ARTIFACT_STATE_KEY] = deduped_names
        logger.info("Saved uploaded files as ADK artifacts: %s", tracked_names)

    return None
