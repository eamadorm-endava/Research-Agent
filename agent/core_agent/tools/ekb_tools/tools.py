import asyncio
import httpx
from typing import Optional
from google.adk.tools import BaseTool, ToolContext
from google.genai import types
from loguru import logger
from typing_extensions import override

from ..security import get_id_token
from .schemas import (
    TriggerEKBPipelineBatchRequest,
    TriggerBatchEKBPipelineResponse,
    SingleTriggerResponse,
    CheckIngestionStatusRequest,
    CheckIngestionStatusResponse,
)

from .config import EKB_TOOLS_CONFIG

CLIENT_LIMITS = httpx.Limits(
    max_keepalive_connections=EKB_TOOLS_CONFIG.MAX_KEEPALIVE_CONNECTIONS,
    max_connections=EKB_TOOLS_CONFIG.MAX_CONNECTIONS,
)


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

    async def _trigger_ekb_pipeline(
        self,
        client: httpx.AsyncClient,
        ekb_url: str,
        headers: dict[str, str],
        gcs_uri: str,
    ) -> SingleTriggerResponse:
        """
        Executes an asynchronous HTTP POST request to trigger the EKB ingestion pipeline for a single URI.
        Catches all exceptions so asyncio.gather never aborts the batch.

        This method signals the backend service to commence the parsing, classification,
        and indexing processes for a specific document stored in the Enterprise Knowledge Base.

        Args:
            client: httpx.AsyncClient -> The shared HTTP client for connection pooling.
            ekb_url: str -> Full URL of the EKB pipeline /ingest endpoint.
            headers: dict[str, str] -> Required authorization and content-type headers.
            gcs_uri: str -> Canonical GCS URI of the document to be ingested.

        Returns:
            SingleTriggerResponse -> The unified result for this single file trigger.
        """
        filename = gcs_uri.split("/")[-1]
        try:
            logger.debug(
                f"Triggering the EKB Pipeline to process the document: {gcs_uri}"
            )
            response = await client.post(
                ekb_url, json={"gcs_uri": gcs_uri}, headers=headers, timeout=120.0
            )

            # Raise exception for HTTP errors to trigger the except block and
            # return execution_status="error" instead of crashing.
            response.raise_for_status()

            data = response.json()
            logger.debug(f"EKB pipeline response for '{gcs_uri}': {data}")

            job_id = data.get("job_id")
            logger.info(
                f"EKB Pipeline triggered successfully for file '{filename}', job_id='{job_id}'"
            )

            return SingleTriggerResponse(
                gcs_uri=gcs_uri,
                job_id=job_id,
                job_status=data.get("status"),
                execution_status="success",
                execution_message=data.get(
                    "message", f"Ingestion started for '{filename}'."
                ),
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"EKB Pipeline Trigger HTTP error for uri='{gcs_uri}': {e}")
            try:
                # Attempt to extract the FastAPI "detail" message from the 4xx/5xx response body
                error_data = e.response.json()
                detail = error_data.get("detail", str(e))
            except Exception:
                # Fallback to the raw exception string if the response isn't valid JSON
                detail = str(e)

            return SingleTriggerResponse(
                gcs_uri=gcs_uri,
                execution_status="error",
                execution_message=f"Pipeline Error: {detail}",
            )
        except Exception as e:
            logger.error(
                f"EKB Pipeline Trigger failed for uri='{gcs_uri}': {type(e).__name__}: {e}"
            )
            return SingleTriggerResponse(
                gcs_uri=gcs_uri,
                execution_status="error",
                execution_message=f"Internal Error: {type(e).__name__}: {e}",
            )

    def _persist_jobs_to_session_state(
        self, tool_context: ToolContext, jobs: list[dict[str, str]]
    ) -> int:
        """
        Appends newly started ingestion jobs to the persistent ADK session state.

        This state is utilized to safely track jobs that have been triggered but haven't
        yet completed. Other tools (like check_ingestion_status) or background callbacks
        can read this state to monitor the progress of pending items.

        Args:
            tool_context: ToolContext -> The agent's context providing access to the session state.
            jobs: list[dict[str, str]] -> A list of job dictionaries (containing 'job_id' and 'filename') to append.

        Returns:
            int -> The updated total number of pending jobs currently tracked in the session state.
        """
        pending = list(
            tool_context.state.get(EKB_TOOLS_CONFIG.SESSION_STATE_PENDING_JOBS_KEY, [])
        )
        pending.extend(jobs)
        tool_context.state[EKB_TOOLS_CONFIG.SESSION_STATE_PENDING_JOBS_KEY] = pending
        return len(pending)

    @override
    async def run_async(self, *, args: dict, tool_context: ToolContext) -> dict:
        """
        Validates the batch request, triggers all pipelines in parallel, and stores
        successful job IDs in session state.

        Args:
            args: dict -> Must contain 'gcs_uris' (list of GCS URIs).
            tool_context: ToolContext -> ADK context for session state storage.

        Returns:
            dict -> Serialised TriggerBatchEKBPipelineResponse containing all individual results.
        """
        raw_uris = args.get("gcs_uris")
        logger.info(
            f"EKB Pipeline Trigger invoked with {len(raw_uris) if isinstance(raw_uris, list) else 0} URI(s)"
        )
        try:
            request = TriggerEKBPipelineBatchRequest(**args)
            ekb_url = f"{EKB_TOOLS_CONFIG.EKB_PIPELINE_URL.strip('/')}/ingest"

            id_token = get_id_token(EKB_TOOLS_CONFIG.EKB_PIPELINE_URL)
            if not id_token:
                logger.error(
                    f"EKB Pipeline Trigger failed: Could not obtain ID token for '{EKB_TOOLS_CONFIG.EKB_PIPELINE_URL}'"
                )

                # Distribute the batch-level auth failure into individual error responses per-URI
                errors = [
                    SingleTriggerResponse(
                        gcs_uri=uri,
                        execution_status="error",
                        execution_message="Authentication failed: Could not obtain ID token.",
                    )
                    for uri in request.gcs_uris
                ]
                return TriggerBatchEKBPipelineResponse(
                    successful_jobs=0,
                    failed_jobs=len(errors),
                    job_responses=errors,
                ).model_dump()
            headers = {
                "Authorization": f"Bearer {id_token}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(limits=CLIENT_LIMITS) as client:
                results: list[SingleTriggerResponse] = await asyncio.gather(
                    *[
                        self._trigger_ekb_pipeline(client, ekb_url, headers, uri)
                        for uri in request.gcs_uris
                    ]
                )

            successful_jobs = [
                {"job_id": r.job_id, "filename": r.gcs_uri.split("/")[-1]}
                for r in results
                if r.execution_status == "success" and r.job_id
            ]

            success_count = len(successful_jobs)
            error_count = len(results) - success_count

            if successful_jobs:
                total_pending = self._persist_jobs_to_session_state(
                    tool_context, successful_jobs
                )
            else:
                total_pending = len(
                    tool_context.state.get(
                        EKB_TOOLS_CONFIG.SESSION_STATE_PENDING_JOBS_KEY, []
                    )
                )

            logger.info(
                f"{success_count} out of {len(results)} triggers were successful, {error_count} errors. Total jobs being processed: {total_pending}"
            )

            return TriggerBatchEKBPipelineResponse(
                successful_jobs=success_count,
                failed_jobs=error_count,
                job_responses=results,
            ).model_dump()

        except Exception as e:
            logger.error(f"Batch EKB Pipeline Trigger failed: {type(e).__name__}: {e}")
            error_msg = f"Internal Error: {type(e).__name__}: {e}"
            uris = raw_uris if isinstance(raw_uris, list) else []
            if not uris:
                return TriggerBatchEKBPipelineResponse(
                    successful_jobs=0,
                    failed_jobs=1,
                    job_responses=[
                        SingleTriggerResponse(
                            gcs_uri="N/A",
                            execution_status="error",
                            execution_message=error_msg,
                        )
                    ],
                ).model_dump()

            errors = [
                SingleTriggerResponse(
                    gcs_uri=uri if isinstance(uri, str) else "N/A",
                    execution_status="error",
                    execution_message=error_msg,
                )
                for uri in uris
            ]
            return TriggerBatchEKBPipelineResponse(
                successful_jobs=0,
                failed_jobs=len(errors),
                job_responses=errors,
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

    async def _fetch_job_status(self, ekb_url: str, headers: dict[str, str]) -> dict:
        """
        GETs the current status of an ingestion job from the EKB service.

        Args:
            ekb_url: str -> Full URL of the /status/{job_id} endpoint.
            headers: dict[str, str] -> Authorization headers.

        Returns:
            dict -> Parsed JSON status response from the pipeline service.
        """
        async with httpx.AsyncClient(limits=CLIENT_LIMITS) as client:
            response = await client.get(ekb_url, headers=headers, timeout=10.0)
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
        logger.info(f"Checking the EKB Pipeline status for job_id='{raw_job_id}'")
        try:
            request = CheckIngestionStatusRequest(**args)
            ekb_url = f"{EKB_TOOLS_CONFIG.EKB_PIPELINE_URL.strip('/')}/status/{request.job_id}"

            id_token = get_id_token(EKB_TOOLS_CONFIG.EKB_PIPELINE_URL)
            if not id_token:
                logger.error(
                    f"EKB Pipeline Status Check failed: Could not obtain ID token for '{EKB_TOOLS_CONFIG.EKB_PIPELINE_URL}'"
                )
                return CheckIngestionStatusResponse(
                    job_id=request.job_id,
                    job_status="Unknown",
                    job_message="Unknown",
                    execution_status="error",
                    execution_message="Authentication failed",
                ).model_dump()
            headers = {
                "Authorization": f"Bearer {id_token}",
                "Content-Type": "application/json",
            }

            data = await self._fetch_job_status(ekb_url, headers)
            logger.debug(f"EKB pipeline status response for '{request.job_id}': {data}")

            status = data.get("status")
            logger.info(
                f"EKB Pipeline status checked successfully for job_id='{request.job_id}', status='{status}'"
            )

            return CheckIngestionStatusResponse(
                execution_status="success",
                execution_message="Successfully retrieved job status.",
                job_id=data.get("job_id", request.job_id),
                job_status=status,
                job_message=data.get("message"),
                gcs_uri=data.get("gcs_uri"),
                chunks_generated=data.get("chunks_generated"),
                final_domain=data.get("final_domain"),
                security_tier=data.get("security_tier"),
            ).model_dump()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"EKB Pipeline Status Check HTTP error for job_id='{raw_job_id}': {e}"
            )
            try:
                # Extract the FastAPI "detail" message (e.g., "Job not found") if the response is JSON
                error_data = e.response.json()
                detail = error_data.get("detail", str(e))
            except Exception:
                # Fallback if the endpoint returned a non-JSON error page
                detail = str(e)

            return CheckIngestionStatusResponse(
                job_id=args.get("job_id", "N/A"),
                job_status="Unknown",
                job_message="Unknown",
                execution_status="error",
                execution_message=f"Pipeline Error: {detail}",
            ).model_dump()

        except Exception as e:
            logger.error(
                f"EKB Pipeline Status Check failed for job_id='{raw_job_id}': {type(e).__name__}: {e}"
            )
            return CheckIngestionStatusResponse(
                job_id=args.get("job_id", "N/A"),
                job_status="Unknown",
                job_message="Unknown",
                execution_status="error",
                execution_message=f"Internal Error: {type(e).__name__}: {e}",
            ).model_dump()
