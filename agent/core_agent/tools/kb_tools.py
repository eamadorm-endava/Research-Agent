import httpx
from typing import Optional
from google.adk.tools import BaseTool, ToolContext
from google.genai import types
from loguru import logger
from typing_extensions import override

from ..config import AGENT_CONFIG
from ..security import get_id_token
from .kb_schemas import (
    TriggerEKBPipelineRequest,
    TriggerEKBPipelineResponse,
    CheckIngestionStatusRequest,
    CheckIngestionStatusResponse,
)

# Key for storing pending jobs in session state
PENDING_INGESTIONS_KEY = "pending_ingestions"


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
                        description="The canonical GCS URI of the document to ingest.",
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
        try:
            request = TriggerEKBPipelineRequest(**args)
            gcs_uri = request.gcs_uri

            url = f"{AGENT_CONFIG.EKB_PIPELINE_URL.strip('/')}/ingest"
            id_token = get_id_token(AGENT_CONFIG.EKB_PIPELINE_URL)

            if not id_token:
                return TriggerEKBPipelineResponse(
                    execution_status="error",
                    execution_message="Authentication failed: Could not obtain ID token.",
                ).model_dump()

            headers = {
                "Authorization": f"Bearer {id_token}",
                "Content-Type": "application/json",
            }
            payload = {"gcs_uri": gcs_uri}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, json=payload, headers=headers, timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

                job_id = data.get("job_id")
                filename = request.filename

                # Store in session state for proactive status checks
                pending = list(tool_context.state.get(PENDING_INGESTIONS_KEY, []))
                pending.append({"job_id": job_id, "filename": filename})
                tool_context.state[PENDING_INGESTIONS_KEY] = pending

                logger.info(f"Ingestion job {job_id} started for {filename}")

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
            logger.error(f"Failed to trigger EKB pipeline: {e}")
            return TriggerEKBPipelineResponse(
                execution_status="error",
                execution_message=f"Internal Error: {str(e)}",
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
        try:
            request = CheckIngestionStatusRequest(**args)
            url = f"{AGENT_CONFIG.EKB_PIPELINE_URL.strip('/')}/status/{request.job_id}"
            id_token = get_id_token(AGENT_CONFIG.EKB_PIPELINE_URL)

            if not id_token:
                return {"execution_status": "error", "execution_message": "Auth failed"}

            headers = {"Authorization": f"Bearer {id_token}"}
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                return CheckIngestionStatusResponse(**data).model_dump()
        except Exception as e:
            return {"execution_status": "error", "execution_message": str(e)}
