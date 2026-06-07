from typing import Optional

from google.adk.tools import BaseTool, ToolContext
from google.genai import types
from loguru import logger
from typing_extensions import override

from ..artifact_management.schemas import (
    GetArtifactUriRequest,
    GetArtifactUriResponse,
)

_MULTIMODAL_PREFIXES = ("image/", "audio/", "video/")
_TEXT_LIKE_TYPES = ("application/json", "application/csv", "application/xml")


class GetArtifactUriTool(BaseTool):
    """Retrieves the canonical GCS URI for a file registered in the current session."""

    def __init__(self) -> None:
        """Registers the tool with its name and description for Gemini function calling."""
        super().__init__(
            name="get_artifact_uri",
            description=(
                "Retrieves the GCS URI for a session artifact by its filename. "
                "Use this when you need the 'gs://' path of a file the user uploaded "
                "to pass it to other storage or processing tools."
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
                    "filename": types.Schema(
                        type=types.Type.STRING,
                        description="The name of the artifact to retrieve the URI for (e.g., 'data.csv').",
                    ),
                    "version": types.Schema(
                        type=types.Type.INTEGER,
                        description="Optional specific version of the artifact.",
                    ),
                },
                required=["filename"],
            ),
        )

    @override
    async def run_async(self, *, args: dict, tool_context: ToolContext) -> dict:
        """Retrieves the GCS URI for the named artifact from the session context.

        Args:
            args: dict -> Must contain 'filename'; optionally 'version'. May be nested under 'request'.
            tool_context: ToolContext -> ADK context for artifact access.

        Returns:
            dict -> Serialised GetArtifactUriResponse.
        """
        try:
            request = GetArtifactUriRequest(**args)
            logger.info(f"Retrieving GCS URI for artifact: {request.filename}")
            artifact_version = await tool_context.get_artifact_version(
                filename=request.filename, version=request.version
            )
            if not artifact_version:
                return GetArtifactUriResponse(
                    gcs_uri=None,
                    execution_status="error",
                    execution_message=f"Artifact '{request.filename}' not found in the current session.",
                ).model_dump()
            return GetArtifactUriResponse(
                gcs_uri=artifact_version.canonical_uri,
                execution_status="success",
                execution_message=f"Successfully retrieved URI for {request.filename}.",
            ).model_dump()
        except Exception as e:
            logger.error(f"Error retrieving artifact URI: {e}")
            return GetArtifactUriResponse(
                gcs_uri=None,
                execution_status="error",
                execution_message=f"Internal error: {str(e)}",
            ).model_dump()
