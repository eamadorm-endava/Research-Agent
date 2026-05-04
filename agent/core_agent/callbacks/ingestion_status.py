import httpx
from google.adk.agents.callback_context import CallbackContext
from google.adk.events.event import Event
from google.genai import types
from loguru import logger

from ..config import AGENT_CONFIG
from ..security import get_id_token
from ..tools.kb_tools import PENDING_INGESTIONS_KEY

from typing import Optional


async def sync_ingestion_status(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    """
    Proactively checks the status of pending ingestion jobs and injects updates into session history.
    This enables proactive notifications in Gemini Enterprise by 'noticing' finished tasks.

    Args:
        callback_context: CallbackContext -> The ADK callback context.

    Returns:
        Optional[types.Content] -> None, to allow the agent to continue its execution.
    """
    pending_jobs = list(callback_context.state.get(PENDING_INGESTIONS_KEY, []))
    if not pending_jobs:
        logger.debug("No pending ingestion jobs to sync.")
        return None

    logger.info(f"Syncing status for {len(pending_jobs)} pending ingestion job(s).")

    still_pending = []
    completed_updates = []

    id_token = get_id_token(AGENT_CONFIG.EKB_PIPELINE_URL)
    if not id_token:
        logger.warning("Skipping status sync: Could not obtain ID token.")
        return None

    headers = {"Authorization": f"Bearer {id_token}"}

    async with httpx.AsyncClient() as client:
        for job in pending_jobs:
            job_id = job.get("job_id")
            filename = job.get("filename")

            try:
                url = f"{AGENT_CONFIG.EKB_PIPELINE_URL.strip('/')}/status/{job_id}"
                response = await client.get(url, headers=headers, timeout=5.0)

                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")

                    if status in ["success", "error"]:
                        logger.info(
                            f"Job {job_id} for {filename} finished with status: {status}"
                        )
                        completed_updates.append(
                            {"filename": filename, "status": status, "details": data}
                        )
                    else:
                        still_pending.append(job)
                else:
                    logger.warning(
                        f"Failed to check status for {job_id}: {response.status_code}"
                    )
                    still_pending.append(job)
            except Exception as e:
                logger.error(f"Error syncing status for job {job_id}: {e}")
                still_pending.append(job)

    # Update session state
    callback_context.state[PENDING_INGESTIONS_KEY] = still_pending

    # If any jobs finished, inject an Event into the session history
    if completed_updates:
        logger.info(
            f"Injecting {len(completed_updates)} completion updates into history."
        )

        update_text = "### [SYSTEM UPDATE: BACKGROUND TASKS]\n"
        for update in completed_updates:
            status_emoji = "✅" if update["status"] == "success" else "❌"
            update_text += (
                f"- {status_emoji} Ingestion of '{update['filename']}' is now {update['status'].upper()}.\n"
                f"  Details: {update['details'].get('message', 'No details available.')}\n"
            )
            if update["status"] == "success":
                update_text += (
                    f"  Domain: {update['details'].get('final_domain')}, "
                    f"Security Tier: {update['details'].get('security_tier')}\n"
                )

        # Create a new Event and append to history
        # We use author='user' with a SYSTEM prefix so the agent treats it as context
        new_event = Event(
            invocation_id=callback_context.invocation_id,
            author="user",
            content=types.Content(role="user", parts=[types.Part(text=update_text)]),
        )

        # ADK 2.0 uses session.events for history
        callback_context.session.events.append(new_event)

        logger.debug(
            f"History updated with {len(completed_updates)} background task results."
        )

    # Always return None to allow the agent to run and see the new history
    return None
