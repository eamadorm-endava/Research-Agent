import asyncio
import httpx
import google.auth
from google.cloud import storage
from typing import Optional
from google.adk.tools import BaseTool, ToolContext
from google.genai import types
from loguru import logger
from typing_extensions import override

from ...security import get_id_token
from .schemas import (
    TriggerEKBPipelineBatchRequest,
    TriggerBatchEKBPipelineResponse,
    SingleTriggerResponse,
    SubmitKBIngestionBatchRequest,
    SubmitKBIngestionFile,
    SubmitKBIngestionBatchResponse,
    SingleSubmitKBIngestionResponse,
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
                            gcs_uri=None,
                            job_id=None,
                            execution_status="error",
                            execution_message=error_msg,
                        )
                    ],
                ).model_dump()

            errors = [
                SingleTriggerResponse(
                    gcs_uri=uri
                    if (
                        isinstance(uri, str)
                        and uri.startswith("gs://")
                        and "/" in uri[5:]
                    )
                    else None,
                    job_id=None,
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


class SubmitKBIngestionBatchTool(BaseTool):
    """Stages confirmed artifacts and starts EKB ingestion with one tool call."""

    def __init__(self) -> None:
        """Registers the unified EKB submission tool."""
        super().__init__(
            name="submit_kb_ingestion_batch",
            description=(
                "Stages user-uploaded PDF artifacts into the KB landing-zone bucket "
                "and triggers the EKB pipeline for the confirmed batch in one call. "
                "Use only after the user has explicitly confirmed the metadata table. "
                "Returns initial job IDs immediately; do not use it for status polling."
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
                    "files": types.Schema(
                        type=types.Type.ARRAY,
                        description="Confirmed files and metadata to submit to the EKB.",
                        items=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "filename": types.Schema(
                                    type=types.Type.STRING,
                                    description="Uploaded PDF artifact filename.",
                                ),
                                "project": types.Schema(
                                    type=types.Type.STRING,
                                    description="User-confirmed EKB project name.",
                                ),
                                "domain": types.Schema(
                                    type=types.Type.STRING,
                                    description="One of IT, Finance, HR, Sales, Executives, Legal, Operations.",
                                ),
                                "trust_level": types.Schema(
                                    type=types.Type.STRING,
                                    description="One of Published, WIP, Archived.",
                                ),
                                "pii_status": types.Schema(
                                    type=types.Type.STRING,
                                    description="User-confirmed PII value: Yes or No.",
                                ),
                                "version": types.Schema(
                                    type=types.Type.INTEGER,
                                    description="Optional artifact version.",
                                ),
                            },
                            required=[
                                "filename",
                                "project",
                                "domain",
                                "trust_level",
                                "pii_status",
                            ],
                        ),
                    ),
                    "destination_bucket": types.Schema(
                        type=types.Type.STRING,
                        description=(
                            "Optional KB landing-zone bucket override. Defaults to "
                            "'<PROJECT_ID>-kb-landing-zone'."
                        ),
                    ),
                },
                required=["files"],
            ),
        )

    @staticmethod
    def _parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
        """
        Splits a canonical GCS URI into bucket and object path.

        Args:
            gcs_uri: str -> Canonical URI using the gs://bucket/object format.

        Returns:
            tuple[str, str] -> Bucket name and object name.
        """
        if not gcs_uri.startswith("gs://") or "/" not in gcs_uri[5:]:
            raise ValueError(f"Invalid GCS URI: {gcs_uri}")
        bucket, object_name = gcs_uri[5:].split("/", 1)
        if not bucket or not object_name:
            raise ValueError(f"Invalid GCS URI: {gcs_uri}")
        return bucket, object_name

    @staticmethod
    def _metadata_for_file(file: SubmitKBIngestionFile) -> dict[str, str]:
        """
        Converts confirmed metadata into the object metadata contract.

        Args:
            file: SubmitKBIngestionFile -> Confirmed file metadata.

        Returns:
            dict[str, str] -> Metadata keys consumed by the EKB pipeline.
        """
        return {
            "project": file.project,
            "domain": file.domain,
            "trust-level": file.trust_level,
            "pii_status": file.pii_status,
        }

    def _make_storage_client(self) -> storage.Client:
        """
        Builds a GCS client from ambient ADC or Cloud Run service account credentials.

        Returns:
            storage.Client -> Authenticated Cloud Storage client.
        """
        credentials, detected_project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return storage.Client(
            credentials=credentials,
            project=detected_project or EKB_TOOLS_CONFIG.PROJECT_ID,
        )

    def _copy_to_kb_landing_zone(
        self,
        client: storage.Client,
        source_bucket_name: str,
        source_object_name: str,
        destination_bucket_name: str,
        destination_object_name: str,
        metadata: dict[str, str],
    ) -> None:
        """
        Copies one artifact to the KB landing-zone bucket and patches metadata.

        Args:
            client: storage.Client -> Authenticated GCS client.
            source_bucket_name: str -> Source bucket name.
            source_object_name: str -> Source object path.
            destination_bucket_name: str -> Destination bucket name.
            destination_object_name: str -> Destination object path.
            metadata: dict[str, str] -> Metadata to attach to the copied object.

        Returns:
            None: The destination object is created and updated in GCS.
        """
        source_bucket = client.bucket(source_bucket_name)
        source_blob = source_bucket.blob(source_object_name)
        destination_bucket = client.bucket(destination_bucket_name)
        copied_blob = source_bucket.copy_blob(
            source_blob, destination_bucket, destination_object_name
        )
        copied_blob.metadata = {**(copied_blob.metadata or {}), **metadata}
        copied_blob.patch()

    async def _stage_file(
        self,
        file: SubmitKBIngestionFile,
        destination_bucket: str,
        storage_client: storage.Client,
        tool_context: ToolContext,
    ) -> SingleSubmitKBIngestionResponse:
        """
        Resolves one session artifact and copies it to the KB landing zone.

        Args:
            file: SubmitKBIngestionFile -> Confirmed file and metadata.
            destination_bucket: str -> KB landing-zone bucket.
            storage_client: storage.Client -> Shared GCS client.
            tool_context: ToolContext -> ADK context for artifact resolution.

        Returns:
            SingleSubmitKBIngestionResponse -> Per-file staging result.
        """
        try:
            artifact_version = await tool_context.get_artifact_version(
                filename=file.filename, version=file.version
            )
            if not artifact_version:
                return SingleSubmitKBIngestionResponse(
                    filename=file.filename,
                    project=file.project,
                    source_uri=None,
                    destination_uri=None,
                    job_id=None,
                    job_status=None,
                    execution_status="error",
                    execution_message=(
                        f"Artifact '{file.filename}' was not found in the current session."
                    ),
                )

            source_uri = artifact_version.canonical_uri
            source_bucket, source_object = self._parse_gcs_uri(source_uri)
            destination_path = f"{file.project.strip('/')}/{file.filename}"
            destination_uri = f"gs://{destination_bucket}/{destination_path}"

            await asyncio.to_thread(
                self._copy_to_kb_landing_zone,
                storage_client,
                source_bucket,
                source_object,
                destination_bucket,
                destination_path,
                self._metadata_for_file(file),
            )

            return SingleSubmitKBIngestionResponse(
                filename=file.filename,
                project=file.project,
                source_uri=source_uri,
                destination_uri=destination_uri,
                job_id=None,
                job_status="STAGED",
                execution_status="success",
                execution_message=f"Successfully staged '{file.filename}'.",
            )
        except Exception as exc:
            logger.error(
                f"Failed to stage '{file.filename}' for EKB ingestion: {type(exc).__name__}: {exc}"
            )
            return SingleSubmitKBIngestionResponse(
                filename=file.filename,
                project=file.project,
                source_uri=None,
                destination_uri=None,
                job_id=None,
                job_status=None,
                execution_status="error",
                execution_message=f"Staging Error: {type(exc).__name__}: {exc}",
            )

    async def _stage_batch(
        self,
        request: SubmitKBIngestionBatchRequest,
        storage_client: storage.Client,
        tool_context: ToolContext,
    ) -> list[SingleSubmitKBIngestionResponse]:
        """
        Stages all confirmed files with bounded concurrency.

        Args:
            request: SubmitKBIngestionBatchRequest -> Batch submission request.
            storage_client: storage.Client -> Shared GCS client.
            tool_context: ToolContext -> ADK context for artifact resolution.

        Returns:
            list[SingleSubmitKBIngestionResponse] -> Per-file staging results.
        """
        destination_bucket = (
            request.destination_bucket
            or EKB_TOOLS_CONFIG.effective_kb_landing_zone_bucket
        )
        semaphore = asyncio.Semaphore(EKB_TOOLS_CONFIG.MAX_SUBMIT_BATCH_CONCURRENCY)

        async def stage_with_limit(
            file: SubmitKBIngestionFile,
        ) -> SingleSubmitKBIngestionResponse:
            async with semaphore:
                return await self._stage_file(
                    file, destination_bucket, storage_client, tool_context
                )

        return await asyncio.gather(*[stage_with_limit(file) for file in request.files])

    @staticmethod
    def _merge_trigger_results(
        staged_results: list[SingleSubmitKBIngestionResponse],
        trigger_result: dict,
    ) -> list[SingleSubmitKBIngestionResponse]:
        """
        Combines staging results with pipeline trigger results by destination URI.

        Args:
            staged_results: list[SingleSubmitKBIngestionResponse] -> Staging results.
            trigger_result: dict -> Output from trigger_ekb_pipeline.

        Returns:
            list[SingleSubmitKBIngestionResponse] -> Final per-file submission results.
        """
        trigger_by_uri = {
            item.get("gcs_uri"): item
            for item in trigger_result.get("job_responses", [])
        }
        merged: list[SingleSubmitKBIngestionResponse] = []
        for staged in staged_results:
            if staged.execution_status != "success" or not staged.destination_uri:
                merged.append(staged)
                continue

            trigger_item = trigger_by_uri.get(staged.destination_uri)
            if not trigger_item:
                merged.append(
                    staged.model_copy(
                        update={
                            "execution_status": "error",
                            "execution_message": "Pipeline Error: no trigger result returned.",
                            "job_status": None,
                        }
                    )
                )
                continue

            merged.append(
                staged.model_copy(
                    update={
                        "job_id": trigger_item.get("job_id"),
                        "job_status": trigger_item.get("job_status"),
                        "execution_status": trigger_item.get(
                            "execution_status", "error"
                        ),
                        "execution_message": trigger_item.get(
                            "execution_message", "Pipeline trigger completed."
                        ),
                    }
                )
            )
        return merged

    @override
    async def run_async(self, *, args: dict, tool_context: ToolContext) -> dict:
        """
        Stages confirmed files and triggers EKB ingestion jobs in a single tool call.

        Args:
            args: dict -> Must contain confirmed files and metadata.
            tool_context: ToolContext -> ADK context for artifact and session state access.

        Returns:
            dict -> Serialised SubmitKBIngestionBatchResponse.
        """
        logger.info("Unified KB ingestion submission invoked")
        try:
            request = SubmitKBIngestionBatchRequest(**args)
            storage_client = self._make_storage_client()
            staged_results = await self._stage_batch(
                request, storage_client, tool_context
            )

            staged_successes = [
                result.destination_uri
                for result in staged_results
                if result.execution_status == "success" and result.destination_uri
            ]

            if staged_successes:
                trigger_result = await TriggerEKBPipelineTool().run_async(
                    args={"gcs_uris": staged_successes}, tool_context=tool_context
                )
                final_results = self._merge_trigger_results(
                    staged_results, trigger_result
                )
            else:
                final_results = staged_results

            successful_jobs = len(
                [
                    result
                    for result in final_results
                    if result.execution_status == "success"
                ]
            )
            failed_jobs = len(final_results) - successful_jobs

            return SubmitKBIngestionBatchResponse(
                successful_jobs=successful_jobs,
                failed_jobs=failed_jobs,
                file_responses=final_results,
            ).model_dump()
        except Exception as exc:
            logger.error(
                f"Unified KB ingestion submission failed: {type(exc).__name__}: {exc}"
            )
            return SubmitKBIngestionBatchResponse(
                successful_jobs=0,
                failed_jobs=1,
                file_responses=[
                    SingleSubmitKBIngestionResponse(
                        filename="N/A",
                        project="N/A",
                        source_uri=None,
                        destination_uri=None,
                        job_id=None,
                        job_status=None,
                        execution_status="error",
                        execution_message=(
                            f"Internal Error: {type(exc).__name__}: {exc}"
                        ),
                    )
                ],
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
