from typing import Optional

from google.adk.agents.context import Context
from google.genai import types
from loguru import logger

PENDING_RENDER_KEY = "pending_artifact_renders"
PENDING_URI_KEY = "pending_gcs_uri_renders"


async def render_pending_artifacts(
    callback_context: Context,
) -> Optional[types.Content]:
    """Unified renderer for both local session artifacts and external GCS URIs.

    Handles:
    1. Local Artifacts (UI Uploads): Queued in PENDING_RENDER_KEY. Loaded as URIs from the Landing Zone.
    2. External URIs (Discovery): Queued in PENDING_URI_KEY. Passed directly as URIs from original buckets.

    Args:
        callback_context: Context -> The ADK callback context with state and artifact access.

    Returns:
        Optional[types.Content] -> Inline content with all pending artifact Parts,
        or None if no artifacts are queued.
    """
    artifact_parts: list[types.Part] = []

    # Path A: Local Artifacts (UI Uploads / Stashed Content)
    pending_filenames: list[str] = callback_context.state.get(PENDING_RENDER_KEY, [])
    if pending_filenames:
        logger.info(f"Rendering {len(pending_filenames)} local artifact(s).")
        artifact_parts.extend(
            await _load_artifact_parts(callback_context, pending_filenames)
        )
        callback_context.state[PENDING_RENDER_KEY] = []

    # Path B: External GCS URIs (GCS Discovery / Direct-Pass)
    pending_uris: list[dict[str, str]] = callback_context.state.get(PENDING_URI_KEY, [])
    if pending_uris:
        logger.info(f"Rendering {len(pending_uris)} external GCS URI(s).")
        for item in pending_uris:
            uri = item.get("uri")
            mime_type = item.get("mime_type", "application/pdf")
            if uri:
                artifact_parts.append(
                    types.Part(
                        file_data=types.FileData(file_uri=uri, mime_type=mime_type)
                    )
                )
        callback_context.state[PENDING_URI_KEY] = []

    if not artifact_parts:
        return None

    logger.debug(f"Combined render complete: {len(artifact_parts)} total parts.")
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
            # Standard load_artifact returns a Part(file_data=...) pointing to the Landing Zone
            artifact_part = await callback_context.load_artifact(filename)

            if artifact_part:
                artifact_parts.append(artifact_part)
                logger.debug(f"Loaded local artifact URI for rendering: {filename}")
            else:
                logger.warning(
                    f"Artifact not found during render, skipping: {filename}"
                )
        except Exception as error:
            logger.error(f"Failed to load artifact '{filename}' for rendering: {error}")
    return artifact_parts
