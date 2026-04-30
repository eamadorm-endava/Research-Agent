from typing import Optional

from google.adk.agents.context import Context
from google.genai import types
from loguru import logger

PENDING_RENDER_KEY = "pending_artifact_renders"


async def render_pending_artifacts(
    callback_context: Context,
) -> Optional[types.Content]:
    """Loads artifacts queued during the agent turn and returns them as inline Parts.

    Gemini Enterprise only renders files returned as inline types.Part objects in
    the final agent response. Tools cannot return Parts directly (causes schema
    parsing errors), so they queue filenames in state under PENDING_RENDER_KEY.
    This callback converts that queue into renderable content before the response
    is sent to the platform.

    Args:
        callback_context: Context -> The ADK callback context with state and artifact access.

    Returns:
        Optional[types.Content] -> Inline content with all pending artifact Parts,
        or None if no artifacts are queued.
    """
    pending_filenames: list[str] = callback_context.state.get(PENDING_RENDER_KEY, [])
    if not pending_filenames:
        return None

    logger.info(
        f"Rendering {len(pending_filenames)} pending artifact(s) for Gemini Enterprise."
    )
    artifact_parts = await _load_artifact_parts(callback_context, pending_filenames)

    callback_context.state[PENDING_RENDER_KEY] = []
    logger.debug("Cleared pending artifact render queue from session state.")

    if not artifact_parts:
        return None

    return types.Content(role="model", parts=artifact_parts)


async def _load_artifact_parts(
    callback_context: Context,
    filenames: list[str],
) -> list[types.Part]:
    """Attempts to load each artifact by filename, skipping any that fail or are missing.

    Args:
        callback_context: Context -> The ADK callback context with artifact access.
        filenames: list[str] -> Artifact filenames to load.

    Returns:
        list[types.Part] -> Successfully loaded Parts (failed loads are skipped).
    """
    artifact_parts = []
    for filename in filenames:
        try:
            # If using StorageService, we must force bytes for GE rendering.
            # Standard load_artifact would return a GCS reference which GE doesn't render.
            storage_service = getattr(
                callback_context.invocation_context, "artifact_service", None
            )
            if storage_service and hasattr(storage_service, "load_artifact_as_bytes"):
                artifact_part = await storage_service.load_artifact_as_bytes(
                    app_name=callback_context.invocation_context.app_name,
                    user_id=callback_context.invocation_context.user_id,
                    session_id=callback_context.invocation_context.session.id,
                    filename=filename,
                )
            else:
                artifact_part = await callback_context.load_artifact(filename)

            if artifact_part:
                artifact_parts.append(artifact_part)
                logger.debug(f"Loaded artifact for GE rendering: {filename}")
            else:
                logger.warning(
                    f"Artifact not found during render, skipping: {filename}"
                )
        except Exception as error:
            logger.error(f"Failed to load artifact '{filename}' for rendering: {error}")
    return artifact_parts
