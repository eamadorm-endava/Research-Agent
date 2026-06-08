import httpx
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.events.event import Event
from google.genai import types
from loguru import logger

from ....security import get_id_token
from ....tools.ekb_tools.config import EKB_TOOLS_CONFIG

# Global client to share connection pool across multiple requests
limits = httpx.Limits(
    max_keepalive_connections=EKB_TOOLS_CONFIG.MAX_KEEPALIVE_CONNECTIONS,
    max_connections=EKB_TOOLS_CONFIG.MAX_CONNECTIONS,
)
http_client = httpx.AsyncClient(limits=limits)


async def _poll_job_status(job_id: str, headers: dict[str, str]) -> Optional[dict]:
    """
    Polls the EKB pipeline for the status of a specific job.

    Args:
        job_id: str -> The ID of the job to check
        headers: dict[str, str] -> The authorization headers

    Returns:
        Optional[dict] -> The job data if finished, otherwise None
    """
    try:
        url = f"{EKB_TOOLS_CONFIG.EKB_PIPELINE_URL.strip('/')}/status/{job_id}"
        logger.debug(f"Checking status for job {job_id} at {url}")
        response = await http_client.get(url, headers=headers, timeout=10.0)

        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            if status in ["success", "error"]:
                return {"status": status, "details": data}

            logger.debug(f"Job {job_id} still in progress (status: {status}).")
            return None

        logger.warning(f"Failed to check status for {job_id}: {response.status_code}")
    except httpx.TimeoutException:
        logger.warning(f"Timeout syncing status for job {job_id} (10s).")
    except httpx.RequestError as exc:
        logger.error(
            f"Network error syncing status for job {job_id} at {exc.request.url}: {exc}"
        )
    except Exception as e:
        logger.error(
            f"Unexpected error syncing status for job {job_id}: {type(e).__name__} - {e}"
        )

    return None


def _inject_completion_events(
    completed_updates: list[dict], callback_context: CallbackContext
) -> None:
    """
    Injects completion updates into the session history.

    Args:
        completed_updates: list[dict] -> The list of completed job updates
        callback_context: CallbackContext -> The ADK callback context

    Returns:
        None -> Modifies the session history in place
    """
    if not completed_updates:
        return

    logger.info(f"Injecting {len(completed_updates)} completion updates into history.")
    update_text = "### [SYSTEM UPDATE: BACKGROUND TASKS]\n"

    for update in completed_updates:
        status_indicator = "[SUCCESS]" if update["status"] == "success" else "[FAILED]"
        filename = update.get("filename", "Unknown")
        details = update.get("details", {})

        action_result = (
            "completed successfully" if update["status"] == "success" else "failed"
        )
        update_text += (
            f"- {status_indicator} Ingestion of '{filename}' has {action_result}.\n"
            f"  Details: {details.get('message', 'No details available.')}\n"
        )
        if update["status"] == "success":
            update_text += (
                f"  Domain: {details.get('final_domain')}, "
                f"Security Tier: {details.get('security_tier')}\n"
                f"  Chunks Generated: {details.get('chunks_generated')}\n"
                f"  Final GCS URI: {details.get('gcs_uri')}\n"
            )

    new_event = Event(
        invocation_id=callback_context.invocation_id,
        author="user",
        content=types.Content(role="user", parts=[types.Part(text=update_text)]),
    )
    callback_context.session.events.append(new_event)
    logger.info(
        f"Proactive history update successful for {len(completed_updates)} jobs."
    )


async def sync_ekb_job_status(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    """
    Proactively checks the status of pending ingestion jobs and injects updates into session history.

    Args:
        callback_context: CallbackContext -> The ADK callback context.

    Returns:
        Optional[types.Content] -> None, to allow the agent to continue its execution.
    """
    pending_jobs: list[dict] = list(
        callback_context.state.get(EKB_TOOLS_CONFIG.SESSION_STATE_PENDING_JOBS_KEY, [])
    )
    if not pending_jobs:
        return None

    id_token = get_id_token(EKB_TOOLS_CONFIG.EKB_PIPELINE_URL)
    if not id_token:
        logger.warning("Skipping status sync: Could not obtain ID token.")
        return None

    headers = {"Authorization": f"Bearer {id_token}"}
    still_pending = []
    completed_updates = []

    for job in pending_jobs:
        job_id = job.get("job_id")
        filename = job.get("filename")

        result = await _poll_job_status(job_id, headers)
        if result:
            logger.info(
                f"Job {job_id} for {filename} finished with status: {result['status']}"
            )
            result["filename"] = filename
            completed_updates.append(result)
        else:
            still_pending.append(job)

    callback_context.state[EKB_TOOLS_CONFIG.SESSION_STATE_PENDING_JOBS_KEY] = (
        still_pending
    )
    _inject_completion_events(completed_updates, callback_context)

    return None
