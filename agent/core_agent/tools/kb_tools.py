import httpx
from typing import Optional
from google.adk.tools import BaseTool, ToolContext
from google.genai import types
from loguru import logger
from typing_extensions import override

from ..config import INGESTION_AGENT_CONFIG as AGENT_CONFIG
from ..security import get_id_token
from .kb_schemas import (
    TriggerEKBPipelineRequest,
    TriggerEKBPipelineResponse,
    CheckIngestionStatusRequest,
    CheckIngestionStatusResponse,
)

# Key for storing pending jobs in session state
PENDING_INGESTIONS_KEY = "pending_ingestions"

_CLIENT_LIMITS = httpx.Limits(max_keepalive_connections=50, max_connections=100)


def _get_bearer_headers(audience: str, tool_name: str) -> Optional[dict[str, str]]:
    """
    Fetches an OIDC token for the given audience and returns bearer auth headers.

    Args:
        audience: str -> The Cloud Run service URL used as the OIDC audience.
        tool_name: str -> Tool identifier used in log messages.

    Returns:
        Optional[dict[str, str]] -> Auth headers dict, or None if token is unavailable.
    """
    id_token = get_id_token(audience)
    if not id_token:
        logger.error(f"[{tool_name}] Could not obtain ID token for '{audience}'")
        return None
    return {"Authorization": f"Bearer {id_token}", "Content-Type": "application/json"}


class TriggerEKBPipelineTool(BaseTool):
    """Triggers the Enterprise Knowledge Base (EKB) ingestion pipeline."""

    def __init__(self) -> None:
        """Registers the tool for background processing of documents."""
        super().__init__(
            name="trigger_ekb_pipeline",
            description=(
                "Finalizes the Enterprise Knowledge Base (EKB) ingestion by triggering "
                "the background processing pipeline (classification, chunking, indexing). "
                "Use this tool ONLY as the final step of the 'kb-file-ingestion' skill "
                "after the file has been successfully moved to the destination bucket."
            ),
        )

    def _get_declaration(self) -> Optional[types.FunctionDeclaration]:
        """
        Builds the Gemini function declaration schema for this tool.

        Returns:
            Optional[types.FunctionDeclaration] -> Schema describing the tool's parameters.
        """
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "gcs_uri": types.Schema(
                        type=types.Type.STRING,
                        description="The canonical GCS URI of the document to ingest (e.g., gs://kb-landing-zone/project/file.pdf)",
                    ),
                },
                required=["gcs_uri"],
            ),
        )

    async def _post_to_ingest(
        self, url: str, headers: dict[str, str], gcs_uri: str
    ) -> dict:
        """
        POSTs the ingestion payload to the EKB pipeline /ingest endpoint.

        Args:
            url: str -> Full URL of the /ingest endpoint.
            headers: dict[str, str] -> Authorization and content-type headers.
            gcs_uri: str -> Canonical GCS URI of the document to ingest.

        Returns:
            dict -> Parsed JSON response body from the pipeline service.
        """
        logger.debug(f"[trigger_ekb_pipeline] POSTing to '{url}': gcs_uri='{gcs_uri}'")
        async with httpx.AsyncClient(limits=_CLIENT_LIMITS) as client:
            response = await client.post(
                url, json={"gcs_uri": gcs_uri}, headers=headers, timeout=120.0
            )
        logger.debug(
            f"[trigger_ekb_pipeline] HTTP {response.status_code} from EKB service."
        )
        response.raise_for_status()
        data = response.json()
        logger.debug(f"[trigger_ekb_pipeline] Response body: {data}")
        return data

    def _store_pending_job(
        self, tool_context: ToolContext, job_id: str, filename: str
    ) -> int:
        """
        Appends a pending job entry to the session state and returns the new total.

        Args:
            tool_context: ToolContext -> ADK context for session state access.
            job_id: str -> The job ID returned by the pipeline service.
            filename: str -> The filename of the document being ingested.

        Returns:
            int -> Total number of pending jobs after appending.
        """
        pending = list(tool_context.state.get(PENDING_INGESTIONS_KEY, []))
        pending.append({"job_id": job_id, "filename": filename})
        tool_context.state[PENDING_INGESTIONS_KEY] = pending
        return len(pending)

    @override
    async def run_async(self, *, args: dict, tool_context: ToolContext) -> dict:
        """
        Calls the EKB pipeline service and stores the job_id in session state.

        Args:
            args: dict -> Must contain 'gcs_uri'.
            tool_context: ToolContext -> ADK context for session state storage.

        Returns:
            dict -> Serialised TriggerEKBPipelineResponse.
        """
        raw_uri = args.get("gcs_uri")
        logger.info(f"[trigger_ekb_pipeline] Invoked with gcs_uri='{raw_uri}'")
        try:
            request = TriggerEKBPipelineRequest(**args)
            logger.debug(
                f"[trigger_ekb_pipeline] Request valid — uri='{request.gcs_uri}', filename='{request.filename}'"
            )
            url = f"{AGENT_CONFIG.EKB_PIPELINE_URL.strip('/')}/ingest"
            headers = _get_bearer_headers(
                AGENT_CONFIG.EKB_PIPELINE_URL, "trigger_ekb_pipeline"
            )
            if not headers:
                return TriggerEKBPipelineResponse(
                    execution_status="error",
                    execution_message="Authentication failed: Could not obtain ID token.",
                    job_id="N/A",
                ).model_dump()

            data = await self._post_to_ingest(url, headers, request.gcs_uri)
            job_id = data.get("job_id")
            total_pending = self._store_pending_job(
                tool_context, job_id, request.filename
            )
            logger.info(
                f"[trigger_ekb_pipeline] Done — job_id='{job_id}', filename='{request.filename}', pending={total_pending}"
            )
            return TriggerEKBPipelineResponse(
                execution_status="success",
                execution_message=(
                    f"I've started the ingestion process for '{request.filename}'. "
                    "It usually takes about 10 minutes to classify and index the document. "
                    "I'll let you know once it's finished!"
                ),
                job_id=job_id,
                response=data,
            ).model_dump()

        except Exception as e:
            logger.opt(exception=True).error(
                f"[trigger_ekb_pipeline] FAILED for uri='{raw_uri}': {type(e).__name__}: {e}"
            )
            return TriggerEKBPipelineResponse(
                execution_status="error",
                execution_message=f"Internal Error: {type(e).__name__}: {e}",
                job_id="N/A",
            ).model_dump()


class CheckIngestionStatusTool(BaseTool):
    """Checks the status of a specific EKB ingestion job."""

    def __init__(self) -> None:
        """Initialises the tool with its name and description."""
        super().__init__(
            name="check_ingestion_status",
            description="Checks the current status of an EKB ingestion job using its Job ID.",
        )

    def _get_declaration(self) -> Optional[types.FunctionDeclaration]:
        """
        Builds the Gemini function declaration schema for this tool.

        Returns:
            Optional[types.FunctionDeclaration] -> Schema describing the tool's parameters.
        """
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "job_id": types.Schema(
                        type=types.Type.STRING,
                        description="The unique Job ID returned when the ingestion was started.",
                    ),
                },
                required=["job_id"],
            ),
        )

    async def _fetch_job_status(self, url: str, headers: dict[str, str]) -> dict:
        """
        GETs the current status of an ingestion job from the EKB service.

        Args:
            url: str -> Full URL of the /status/{job_id} endpoint.
            headers: dict[str, str] -> Authorization headers.

        Returns:
            dict -> Parsed JSON status response from the pipeline service.
        """
        async with httpx.AsyncClient(limits=_CLIENT_LIMITS) as client:
            response = await client.get(url, headers=headers, timeout=10.0)
        response.raise_for_status()
        return response.json()

    @override
    async def run_async(self, *, args: dict, tool_context: ToolContext) -> dict:
        """
        Fetches the current status of an ingestion job from the EKB service.

        Args:
            args: dict -> Must contain 'job_id'.
            tool_context: ToolContext -> ADK context for authentication.

        Returns:
            dict -> Serialised CheckIngestionStatusResponse.
        """
        raw_job_id = args.get("job_id")
        logger.info(f"[check_ingestion_status] Invoked with job_id='{raw_job_id}'")
        try:
            request = CheckIngestionStatusRequest(**args)
            logger.debug(
                f"[check_ingestion_status] Request valid — job_id='{request.job_id}'"
            )
            url = f"{AGENT_CONFIG.EKB_PIPELINE_URL.strip('/')}/status/{request.job_id}"
            headers = _get_bearer_headers(
                AGENT_CONFIG.EKB_PIPELINE_URL, "check_ingestion_status"
            )
            if not headers:
                return CheckIngestionStatusResponse(
                    job_id=request.job_id,
                    status="error",
                    message="Auth failed: Could not obtain ID token.",
                    execution_status="error",
                    execution_message="Authentication failed",
                ).model_dump()

            data = await self._fetch_job_status(url, headers)
            logger.info(
                f"[check_ingestion_status] job_id='{request.job_id}' → status='{data.get('status')}'"
            )
            return CheckIngestionStatusResponse(**data).model_dump()

        except Exception as e:
            logger.opt(exception=True).error(
                f"[check_ingestion_status] FAILED for job_id='{raw_job_id}': {type(e).__name__}: {e}"
            )
            return CheckIngestionStatusResponse(
                job_id=args.get("job_id", "N/A"),
                status="error",
                message=str(e),
                execution_status="error",
                execution_message=f"Internal Error: {type(e).__name__}: {e}",
            ).model_dump()
