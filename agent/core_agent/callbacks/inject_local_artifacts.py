from typing import Optional

from google.adk.agents.context import Context
from google.genai import types
from loguru import logger

from ..artifact_management.schemas import PENDING_UI_ARTIFACTS_QUEUE


async def inject_local_artifacts(
    callback_context: Context,
) -> Optional[types.Content]:
    """Unified renderer for local session artifacts uploaded via UI.

    How it works:
    1. The Frontend Upload: When a user uploads a file through the UI, it is uploaded directly to a GCS Landing Zone. The filename is appended to the PENDING_UI_ARTIFACTS_QUEUE in the session state.
    2. The Interception: Registered as a before_agent_callback, this function runs right before the agent processes a new turn and checks the queue for pending filenames.
    3. Zero-Copy Loading via Dependency Injection: For each pending filename, it calls the ADK's native load_artifact(). Crucially, because
       AppBuilder injects the custom StorageService as the global artifact_service, this call is safely delegated. It generates a lightweight Gemini types.Part object
       containing a file_uri pointing directly to the GCS location, without downloading the raw file bytes to memory.
    4. Context Injection & Cleanup: These lightweight Part objects are packaged into a unified Content block and injected straight into the LLM's multimodal context window. The queue is then cleared to prevent duplicate injections on subsequent turns.

    Args:
        callback_context: Context -> The ADK callback context with state and artifact access.

    Returns:
        Optional[types.Content] -> Inline content with all pending artifact Parts, or None if no artifacts are queued.
    """
    artifact_parts: list[types.Part] = []

    # Local Artifacts (UI Uploads / Stashed Content)
    pending_filenames: list[str] = callback_context.state.get(
        PENDING_UI_ARTIFACTS_QUEUE, []
    )
    if pending_filenames:
        logger.info(f"Rendering {len(pending_filenames)} local artifact(s).")
        artifact_parts.extend(
            await _load_artifact_parts(callback_context, pending_filenames)
        )
        callback_context.state[PENDING_UI_ARTIFACTS_QUEUE] = []

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
            # Standard load_artifact is safely delegated to the custom StorageService
            # (injected via AppBuilder). This overrides the native behavior, ensuring it
            # returns a Part(file_data=...) with a gs:// URI reference instead of raw bytes.
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
