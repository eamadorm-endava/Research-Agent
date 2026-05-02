import httpx
from typing import Optional
from google.adk.tools import BaseTool, ToolContext
from google.genai import types
from loguru import logger
from typing_extensions import override

from ..config import AGENT_CONFIG
from ..security import get_id_token
from .kb_schemas import TriggerEKBPipelineRequest, TriggerEKBPipelineResponse


class TriggerEKBPipelineTool(BaseTool):
    """Triggers the Enterprise Knowledge Base (EKB) ingestion pipeline for a given GCS URI."""

    def __init__(self) -> None:
        """Registers the tool with its name and description for Gemini function calling."""
        super().__init__(
            name="trigger_ekb_pipeline",
            description=(
                "Triggers the Enterprise Knowledge Base (EKB) ingestion pipeline. "
                "Use this after moving a file to the 'kb-landing-zone' bucket. "
                "The pipeline will classify, chunk, and index the document for RAG."
            ),
        )

    def _get_declaration(self) -> Optional[types.FunctionDeclaration]:
        """Builds the Gemini function declaration schema for this tool.

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
                        description="The canonical GCS URI of the document to ingest (e.g., gs://kb-landing-zone/project/file.pdf).",
                    ),
                },
                required=["gcs_uri"],
            ),
        )

    @override
    async def run_async(self, *, args: dict, tool_context: ToolContext) -> dict:
        """Calls the EKB pipeline Cloud Run service via HTTP POST.

        Args:
            args: dict -> Must contain 'gcs_uri'.
            tool_context: ToolContext -> ADK context.

        Returns:
            dict -> Serialized TriggerEKBPipelineResponse.
        """
        try:
            request = TriggerEKBPipelineRequest(**args)
            gcs_uri = request.gcs_uri

            url = f"{AGENT_CONFIG.EKB_PIPELINE_URL.strip('/')}/ingest"
            logger.info(f"Triggering EKB pipeline at {url} for {gcs_uri}")

            # Get ID token for Cloud Run authentication
            id_token = get_id_token(AGENT_CONFIG.EKB_PIPELINE_URL)
            if not id_token:
                logger.error(
                    "Failed to obtain ID token for EKB pipeline authentication."
                )
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
                    url, json=payload, headers=headers, timeout=300.0
                )
                response.raise_for_status()
                data = response.json()
                logger.info(f"EKB pipeline triggered successfully: {data}")
                return TriggerEKBPipelineResponse(
                    execution_status="success",
                    execution_message=f"Pipeline triggered successfully for {gcs_uri}.",
                    response=data,
                ).model_dump()
        except Exception as e:
            logger.error(f"Failed to trigger EKB pipeline: {e}")
            return TriggerEKBPipelineResponse(
                execution_status="error",
                execution_message=f"Internal Error: {str(e)}",
            ).model_dump()
