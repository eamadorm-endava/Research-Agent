from typing import Annotated, Optional
from pydantic import Field, BaseModel
from google.adk.tools import BaseTool, ToolContext
from google.genai import types
from typing_extensions import override
from loguru import logger


class GetArtifactUriRequest(BaseModel):
    filename: Annotated[
        str,
        Field(
            description="The name of the artifact to retrieve the URI for (e.g., 'data.csv')."
        ),
    ]
    version: Annotated[
        Optional[int],
        Field(default=None, description="Optional specific version of the artifact."),
    ]


class GetArtifactUriResponse(BaseModel):
    gcs_uri: Annotated[
        Optional[str], Field(description="The full GCS URI (gs://...) of the artifact.")
    ]
    execution_status: Annotated[str, Field(description="Status of the tool execution.")]
    execution_message: Annotated[str, Field(description="Details about the execution.")]


class GetArtifactUriTool(BaseTool):
    """
    A native ADK tool that retrieves the GCS URI for a session artifact.
    This allows the agent to pass the URI to other GCS-aware tools.
    """

    def __init__(self):
        super().__init__(
            name="get_artifact_uri",
            description=(
                "Retrieves the GCS URI for a session artifact by its filename. "
                "Use this when you need the 'gs://' path of a file the user uploaded "
                "to pass it to other storage or processing tools."
            ),
        )

    def _get_declaration(self) -> types.FunctionDeclaration | None:
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
        filename = args.get("filename")
        version = args.get("version")

        logger.info(f"Retrieving GCS URI for artifact: {filename}")

        try:
            artifact_version = await tool_context.get_artifact_version(
                filename=filename, version=version
            )

            if not artifact_version:
                return GetArtifactUriResponse(
                    gcs_uri=None,
                    execution_status="error",
                    execution_message=f"Artifact '{filename}' not found in the current session.",
                ).model_dump()

            return GetArtifactUriResponse(
                gcs_uri=artifact_version.canonical_uri,
                execution_status="success",
                execution_message=f"Successfully retrieved URI for {filename}.",
            ).model_dump()

        except Exception as e:
            logger.error(f"Error retrieving artifact URI: {e}")
            return GetArtifactUriResponse(
                gcs_uri=None,
                execution_status="error",
                execution_message=f"Internal error: {str(e)}",
            ).model_dump()
