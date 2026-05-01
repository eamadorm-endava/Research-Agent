import mimetypes
from typing import Optional

from google.adk.tools import BaseTool, ToolContext
from google.genai import types
from loguru import logger
from typing_extensions import override

from ..artifact_management.schemas import (
    PENDING_URI_KEY,
    GetArtifactUriRequest,
    GetArtifactUriResponse,
    ImportGcsToArtifactRequest,
    ImportGcsToArtifactResponse,
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


class ImportGcsToArtifactTool(BaseTool):
    """Downloads a GCS object and registers it as an ADK session artifact for in-context analysis."""

    def __init__(self) -> None:
        """Registers the tool with its name and description for Gemini function calling."""
        super().__init__(
            name="import_gcs_to_artifact",
            description=(
                "Registers an object from Google Cloud Storage into the current session "
                "context using its original URI reference. Use this when you have a 'gs://' "
                "URI and its MIME type (retrieved from the GCS MCP server) to analyze "
                "content (PDF, Image, Video, etc.) without downloading or copying bytes. "
                "This enables zero-copy analysis of external data."
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
                        description="The canonical GCS URI of the object to import (e.g., gs://bucket/file.pdf).",
                    ),
                    "artifact_name": types.Schema(
                        type=types.Type.STRING,
                        description="Optional custom name for the artifact in the session.",
                    ),
                    "mime_type": types.Schema(
                        type=types.Type.STRING,
                        description="Optional MIME type of the object (e.g., application/pdf). If not provided, it will be guessed.",
                    ),
                },
                required=["gcs_uri"],
            ),
        )

    @override
    async def run_async(self, *, args: dict, tool_context: ToolContext) -> dict:
        """Registers a GCS URI as a session artifact using MCP-provided metadata.

        Args:
            args: dict -> Must contain 'gcs_uri'; optionally 'artifact_name' and 'mime_type'.
            tool_context: ToolContext -> ADK context for artifact saving.

        Returns:
            dict -> Serialised ImportGcsToArtifactResponse.
        """
        try:
            request = ImportGcsToArtifactRequest(**args)
            logger.info(f"Registering GCS URI artifact: {request.gcs_uri}")

            # Extract artifact name from URI if not provided
            object_name = request.gcs_uri[5:].split("/", 1)[-1]
            artifact_name = request.artifact_name or object_name.split("/")[-1]

            # Resolve MIME type: trust input -> guess from extension -> fallback
            mime_type = request.mime_type
            if not mime_type:
                mime_type, _ = mimetypes.guess_type(artifact_name)
                logger.debug(f"MIME type guessed from filename: {mime_type}")
            mime_type = mime_type or "application/octet-stream"

            # Zero-Copy Ingestion: Queue the original URI for the post-turn callback
            # instead of copying it to the session landing zone.
            pending_uris = list(tool_context.state.get(PENDING_URI_KEY, []))
            pending_uris.append({"uri": request.gcs_uri, "mime_type": mime_type})
            tool_context.state[PENDING_URI_KEY] = pending_uris

            logger.info(f"Queued GCS URI for direct LLM ingestion: {request.gcs_uri}")

            return ImportGcsToArtifactResponse(
                artifact_id=f"{artifact_name}:direct",
                gcs_uri=request.gcs_uri,
                content_type=mime_type,
                execution_status="success",
                execution_message=(
                    f"Successfully registered {request.gcs_uri} for direct analysis. "
                    "The model will access the file directly from its original bucket "
                    "without any intermediate copies."
                ),
            ).model_dump()
        except Exception as e:
            logger.error(f"Error registering GCS artifact: {e}")
            return ImportGcsToArtifactResponse(
                artifact_id="",
                gcs_uri=None,
                execution_status="error",
                execution_message=f"Internal error: {str(e)}",
            ).model_dump()

    def _create_artifact_part(
        self, gcs_uri: str, mime_type: str, artifact_name: str
    ) -> types.Part:
        """Creates a Gemini Part using the GCS URI (file_data) without binary downloads.

        Args:
            gcs_uri: str -> The canonical GCS URI.
            mime_type: str -> MIME type for Gemini ingestion.
            artifact_name: str -> Filename for logging.

        Returns:
            types.Part -> Gemini-compatible content part referencing the GCS URI.
        """
        logger.debug(f"Creating URI-based part for {artifact_name} ({mime_type})")
        return types.Part(
            file_data=types.FileData(file_uri=gcs_uri, mime_type=mime_type)
        )
