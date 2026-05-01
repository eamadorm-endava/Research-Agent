import httpx
from typing import Optional
from google.adk.tools import BaseTool, ToolContext
from google.genai import types
from loguru import logger
from typing_extensions import override

from ..config import AGENT_CONFIG
from ..security import get_id_token


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
            tool_context: ToolContext -> ADK context (not directly used here but required by signature).

        Returns:
            dict -> The response from the pipeline service.
        """
        gcs_uri = args.get("gcs_uri")
        if not gcs_uri:
            return {
                "execution_status": "error",
                "execution_message": "Missing 'gcs_uri' parameter.",
            }

        url = f"{AGENT_CONFIG.EKB_PIPELINE_URL}/ingest"
        logger.info(f"Triggering EKB pipeline at {url} for {gcs_uri}")

        # Get ID token for Cloud Run authentication
        id_token = get_id_token(AGENT_CONFIG.EKB_PIPELINE_URL)
        if not id_token:
            logger.error("Failed to obtain ID token for EKB pipeline authentication.")
            return {
                "execution_status": "error",
                "execution_message": "Authentication failed: Could not obtain ID token.",
            }

        headers = {
            "Authorization": f"Bearer {id_token}",
            "Content-Type": "application/json",
        }
        payload = {"gcs_uri": gcs_uri}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, json=payload, headers=headers, timeout=60.0
                )
                response.raise_for_status()
                data = response.json()
                logger.info(f"EKB pipeline triggered successfully: {data}")
                return {
                    "execution_status": "success",
                    "execution_message": f"Pipeline triggered successfully for {gcs_uri}.",
                    "response": data,
                }
        except httpx.HTTPStatusError as e:
            logger.error(f"EKB pipeline service returned an error: {e.response.text}")
            return {
                "execution_status": "error",
                "execution_message": f"Service Error ({e.response.status_code}): {e.response.text}",
            }
        except Exception as e:
            logger.error(f"Failed to trigger EKB pipeline: {e}")
            return {
                "execution_status": "error",
                "execution_message": f"Internal Error: {str(e)}",
            }
