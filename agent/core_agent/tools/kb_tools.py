import asyncio
import httpx
from typing import Optional
from google.adk.tools import BaseTool, ToolContext
from google.genai import types
from loguru import logger
from typing_extensions import override

from ..config import INGESTION_AGENT_CONFIG as AGENT_CONFIG
from ..security import get_id_token
from .kb_schemas import (
    TriggerEKBPipelineBatchRequest,
    TriggerEKBPipelineResponse,
    CheckIngestionStatusRequest,
    CheckIngestionStatusResponse,
)

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
    """Triggers the EKB ingestion pipeline for one or more files in parallel."""

    def __init__(self) -> None:
        """Registers the tool for parallel background processing of documents."""
        super().__init__(
            name="trigger_ekb_pipeline",
            description=(
                "Finalizes the Enterprise Knowledge Base (EKB) ingestion by triggering "
                "the background processing pipeline (classification, chunking, indexing) "
                "for one or more files simultaneously. "
                "Use this tool ONLY as the final step of the 'kb-file-ingestion' skill "
                "after all files have been successfully moved to the destination bucket. "
                "Returns a list of results, one per file."
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
                    "gcs_uris": types.Schema(
                        type=types.Type.ARRAY,
                        description="One or more canonical GCS URIs to ingest (e.g., gs://<project_id>-kb-landing-zone/project/file.pdf)",
                        items=types.Schema(type=types.Type.STRING),
                    ),
                },
                required=["gcs_uris"],
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

    def _store_pending_jobs(
        self, tool_context: ToolContext, jobs: list[dict[str, str]]
    ) -> int:
        """
        Extends the session-state pending jobs list and returns the new total.

        Args:
            tool_context: ToolContext -> ADK context for session state access.
            jobs: list[dict[str, str]] -> Entries with 'job_id' and 'filename' to append.

        Returns:
            int -> Total number of pending jobs after extending.
        """
        pending = list(tool_context.state.get(PENDING_INGESTIONS_KEY, []))
        pending.extend(jobs)
        tool_context.state[PENDING_INGESTIONS_KEY] = pending
        return len(pending)

    async def _trigger_single(
        self, url: str, headers: dict[str, str], gcs_uri: str
    ) -> dict:
        """
        Triggers the pipeline for one URI and returns a per-file result dict.
        Catches all exceptions so asyncio.gather never aborts the batch.

        Args:
            url: str -> Full URL of the /ingest endpoint.
            headers: dict[str, str] -> Authorization and content-type headers.
            gcs_uri: str -> Canonical GCS URI of the document to ingest.

        Returns:
            dict -> Serialised TriggerEKBPipelineResponse for this file.
        """
        filename = gcs_uri.split("/")[-1]
        try:
            data = await self._post_to_ingest(url, headers, gcs_uri)
            job_id = data.get("job_id", "N/A")
            logger.info(
                f"[trigger_ekb_pipeline] Done — job_id='{job_id}', filename='{filename}'"
            )
            return TriggerEKBPipelineResponse(
                execution_status="success",
                execution_message=(
                    f"Ingestion started for '{filename}'. "
                    "Classification and indexing usually takes about 10 minutes."
                ),
                job_id=job_id,
                gcs_uri=gcs_uri,
                response=data,
            ).model_dump()
        except Exception as e:
            logger.opt(exception=True).error(
                f"[trigger_ekb_pipeline] FAILED for uri='{gcs_uri}': {type(e).__name__}: {e}"
            )
            return TriggerEKBPipelineResponse(
                execution_status="error",
                execution_message=f"Internal Error: {type(e).__name__}: {e}",
                job_id="N/A",
                gcs_uri=gcs_uri,
            ).model_dump()

    @override
    async def run_async(self, *, args: dict, tool_context: ToolContext) -> list[dict]:
        """
        Validates the batch request, triggers all pipelines in parallel, and stores
        successful job IDs in session state.

        Args:
            args: dict -> Must contain 'gcs_uris' (list of GCS URIs).
            tool_context: ToolContext -> ADK context for session state storage.

        Returns:
            list[dict] -> One serialised TriggerEKBPipelineResponse per input URI.
        """
        raw_uris = args.get("gcs_uris")
        logger.info(
            f"[trigger_ekb_pipeline] Invoked with {len(raw_uris) if isinstance(raw_uris, list) else 0} URI(s)"
        )
        try:
            request = TriggerEKBPipelineBatchRequest(**args)
            url = f"{AGENT_CONFIG.EKB_PIPELINE_URL.strip('/')}/ingest"
            headers = _get_bearer_headers(
                AGENT_CONFIG.EKB_PIPELINE_URL, "trigger_ekb_pipeline"
            )
            if not headers:
                return [
                    TriggerEKBPipelineResponse(
                        execution_status="error",
                        execution_message="Authentication failed: Could not obtain ID token.",
                        job_id="N/A",
                        gcs_uri=uri,
                    ).model_dump()
                    for uri in request.gcs_uris
                ]

            results: list[dict] = await asyncio.gather(
                *[self._trigger_single(url, headers, uri) for uri in request.gcs_uris]
            )

            successful_jobs = [
                {"job_id": r["job_id"], "filename": r["gcs_uri"].split("/")[-1]}
                for r in results
                if r["execution_status"] == "success" and r.get("gcs_uri")
            ]
            if successful_jobs:
                total = self._store_pending_jobs(tool_context, successful_jobs)
                logger.info(
                    f"[trigger_ekb_pipeline] {len(successful_jobs)} job(s) stored — total pending: {total}"
                )

            return results

        except Exception as e:
            logger.opt(exception=True).error(
                f"[trigger_ekb_pipeline] Batch FAILED: {type(e).__name__}: {e}"
            )
            error_msg = f"Internal Error: {type(e).__name__}: {e}"
            uris = raw_uris if isinstance(raw_uris, list) else []
            if uris:
                return [
                    TriggerEKBPipelineResponse(
                        execution_status="error",
                        execution_message=error_msg,
                        job_id="N/A",
                        gcs_uri=uri if isinstance(uri, str) else None,
                    ).model_dump()
                    for uri in uris
                ]
            return [
                TriggerEKBPipelineResponse(
                    execution_status="error",
                    execution_message=error_msg,
                    job_id="N/A",
                ).model_dump()
            ]


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
