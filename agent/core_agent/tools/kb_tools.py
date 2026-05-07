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

# Connection pool limits for outbound HTTP requests
_CLIENT_LIMITS = httpx.Limits(max_keepalive_connections=50, max_connections=100)


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
            # Step 1: Validate and parse input via Pydantic schema
            logger.debug(
                "[trigger_ekb_pipeline] Step 1/5: Validating request schema..."
            )
            request = TriggerEKBPipelineRequest(**args)
            gcs_uri = request.gcs_uri
            filename = request.filename
            logger.debug(
                f"[trigger_ekb_pipeline] Step 1/5: Schema valid. URI='{gcs_uri}', filename='{filename}'"
            )

            # Step 2: Resolve target URL
            url = f"{AGENT_CONFIG.EKB_PIPELINE_URL.strip('/')}/ingest"
            logger.debug(
                f"[trigger_ekb_pipeline] Step 2/5: Target URL resolved to '{url}'"
            )

            # Step 3: Obtain OIDC identity token
            logger.debug(
                "[trigger_ekb_pipeline] Step 3/5: Fetching OIDC identity token..."
            )
            id_token = get_id_token(AGENT_CONFIG.EKB_PIPELINE_URL)
            if not id_token:
                logger.error(
                    "[trigger_ekb_pipeline] Step 3/5: FAILED — could not obtain ID token. "
                    f"Target audience: '{AGENT_CONFIG.EKB_PIPELINE_URL}'"
                )
                return TriggerEKBPipelineResponse(
                    execution_status="error",
                    execution_message="Authentication failed: Could not obtain ID token.",
                    job_id="N/A",
                ).model_dump()
            logger.debug(
                "[trigger_ekb_pipeline] Step 3/5: ID token obtained successfully."
            )

            # Step 4: POST to Cloud Run /ingest
            headers = {
                "Authorization": f"Bearer {id_token}",
                "Content-Type": "application/json",
            }
            payload = {"gcs_uri": gcs_uri}
            logger.debug(
                f"[trigger_ekb_pipeline] Step 4/5: POSTing payload to '{url}': {payload}"
            )

            async with httpx.AsyncClient(limits=_CLIENT_LIMITS) as client:
                response = await client.post(
                    url, json=payload, headers=headers, timeout=30.0
                )

            logger.debug(
                f"[trigger_ekb_pipeline] Step 4/5: Received HTTP {response.status_code} from EKB service."
            )
            response.raise_for_status()
            data = response.json()
            logger.debug(f"[trigger_ekb_pipeline] Step 4/5: Response body: {data}")

            # Step 5: Persist job in session state
            job_id = data.get("job_id")
            logger.debug(
                f"[trigger_ekb_pipeline] Step 5/5: Persisting job_id='{job_id}' for file='{filename}' in session state..."
            )
            pending = list(tool_context.state.get(PENDING_INGESTIONS_KEY, []))
            pending.append({"job_id": job_id, "filename": filename})
            tool_context.state[PENDING_INGESTIONS_KEY] = pending

            logger.info(
                f"[trigger_ekb_pipeline] Step 5/5: Done. job_id='{job_id}', filename='{filename}'. "
                f"Total pending jobs in state: {len(pending)}"
            )

            return TriggerEKBPipelineResponse(
                execution_status="success",
                execution_message=(
                    f"I've started the ingestion process for '{filename}'. "
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
                execution_message=f"Internal Error: {str(e)}",
                job_id="N/A",
            ).model_dump()


class CheckIngestionStatusTool(BaseTool):
    """Checks the status of a specific EKB ingestion job."""

    def __init__(self) -> None:
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
            # Step 1: Validate input
            logger.debug(
                "[check_ingestion_status] Step 1/3: Validating request schema..."
            )
            request = CheckIngestionStatusRequest(**args)
            logger.debug(
                f"[check_ingestion_status] Step 1/3: Schema valid. job_id='{request.job_id}'"
            )

            # Step 2: Resolve URL and obtain auth token
            url = f"{AGENT_CONFIG.EKB_PIPELINE_URL.strip('/')}/status/{request.job_id}"
            logger.debug(f"[check_ingestion_status] Step 2/3: Status URL='{url}'")

            logger.debug(
                "[check_ingestion_status] Step 2/3: Fetching OIDC identity token..."
            )
            id_token = get_id_token(AGENT_CONFIG.EKB_PIPELINE_URL)
            if not id_token:
                logger.error(
                    "[check_ingestion_status] Step 2/3: FAILED — could not obtain ID token. "
                    f"Target audience: '{AGENT_CONFIG.EKB_PIPELINE_URL}'"
                )
                return CheckIngestionStatusResponse(
                    job_id=request.job_id,
                    status="error",
                    message="Auth failed: Could not obtain ID token.",
                    execution_status="error",
                    execution_message="Authentication failed",
                ).model_dump()
            logger.debug("[check_ingestion_status] Step 2/3: ID token obtained.")

            # Step 3: GET status from EKB service
            headers = {"Authorization": f"Bearer {id_token}"}
            logger.debug(
                f"[check_ingestion_status] Step 3/3: GETting status for job_id='{request.job_id}'..."
            )
            async with httpx.AsyncClient(limits=_CLIENT_LIMITS) as client:
                response = await client.get(url, headers=headers, timeout=10.0)

            logger.debug(
                f"[check_ingestion_status] Step 3/3: Received HTTP {response.status_code} for job_id='{request.job_id}'."
            )
            response.raise_for_status()
            data = response.json()
            job_status = data.get("status")
            logger.info(
                f"[check_ingestion_status] Step 3/3: job_id='{request.job_id}' → status='{job_status}'"
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
                execution_message="Internal Error",
            ).model_dump()
