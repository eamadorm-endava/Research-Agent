import httpx
from google.adk.agents.callback_context import CallbackContext
from google.adk.events.event import Event
from google.genai import types
from loguru import logger

from ..config import AGENT_CONFIG
from ..security import get_id_token
from ..tools.kb_tools import PENDING_INGESTIONS_KEY

from typing import Optional

# Global client to share connection pool across multiple requests
limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
http_client = httpx.AsyncClient(limits=limits)


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
        logger.debug("No pending ingestion jobs in session state.")
        return

    logger.info(
        f"Syncing status for {len(pending_jobs)} pending ingestion job(s): {[j.get('filename') for j in pending_jobs]}"
    )

    still_pending = []
    completed_updates = []

    id_token = get_id_token(AGENT_CONFIG.EKB_PIPELINE_URL)
    if not id_token:
        logger.warning("Skipping status sync: Could not obtain ID token.")
        return

    headers = {"Authorization": f"Bearer {id_token}"}

    for job in pending_jobs:
        job_id = job.get("job_id")
        filename = job.get("filename")

        try:
            url = f"{AGENT_CONFIG.EKB_PIPELINE_URL.strip('/')}/status/{job_id}"
            logger.debug(f"Checking status for job {job_id} at {url}")
            response = await http_client.get(url, headers=headers, timeout=10.0)

            logger.debug(f"Status for job {job_id}: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                logger.debug(f"Status for job {job_id}: {status}")

                if status in ["success", "error"]:
                    logger.info(
                        f"Job {job_id} for {filename} finished with status: {status}"
                    )
                    completed_updates.append(
                        {"filename": filename, "status": status, "details": data}
                    )
                    logger.debug(
                        f"Job {job_id} added to completed_updates. Current count: {len(completed_updates)}"
                    )
                else:
                    logger.debug(f"Job {job_id} still in progress (status: {status}).")
                    still_pending.append(job)
            else:
                logger.warning(
                    f"Failed to check status for {job_id}: {response.status_code}"
                )
                still_pending.append(job)
        except httpx.TimeoutException:
            logger.warning(f"Timeout syncing status for job {job_id} (5s).")
            still_pending.append(job)
        except httpx.RequestError as exc:
            logger.error(
                f"Network error syncing status for job {job_id} at {exc.request.url}: {exc}"
            )
            still_pending.append(job)
        except Exception as e:
            logger.error(
                f"Unexpected error syncing status for job {job_id}: {type(e).__name__} - {e}"
            )
            still_pending.append(job)

    # Update session state
    callback_context.state[PENDING_INGESTIONS_KEY] = still_pending
    logger.debug(
        f"Updated session state: {len(still_pending)} jobs remaining in pending list."
    )

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

        logger.info(
            f"Proactive history update successful for {len(completed_updates)} jobs."
        )

    # Always return None to allow the agent to run and see the new history
    logger.debug("Ingestion sync cycle completed.")
    return
