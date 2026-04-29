import mimetypes
from typing import Optional

from google.adk.tools import BaseTool, ToolContext
from google.cloud import storage
from google.genai import types
from loguru import logger
from typing_extensions import override

from .callbacks import PENDING_RENDER_KEY
from .schemas import (
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
                "Imports an object from Google Cloud Storage into the current session "
                "as an artifact. Use this when you have a 'gs://' URI (e.g., from "
                "reading a file) and you want to analyze its content (PDF, Image, Video, etc.)."
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
        """Downloads the GCS object, converts it to the appropriate Part type, and saves it as an artifact.

        Args:
            args: dict -> Must contain 'gcs_uri'; optionally 'artifact_name' and 'mime_type'. May be nested under 'request'.
            tool_context: ToolContext -> ADK context for artifact saving.

        Returns:
            dict -> Serialised ImportGcsToArtifactResponse.
        """
        try:
            request = ImportGcsToArtifactRequest(**args)
            logger.info(f"Importing GCS object to artifact: {request.gcs_uri}")
            download = self._download_gcs_object(request)
            artifact_part = self._create_artifact_part(
                download["content_bytes"],
                download["mime_type"],
                download["artifact_name"],
            )
            version = await tool_context.save_artifact(
                filename=download["artifact_name"], artifact=artifact_part
            )
            pending = list(tool_context.state.get(PENDING_RENDER_KEY, []))
            pending.append(download["artifact_name"])
            tool_context.state[PENDING_RENDER_KEY] = pending
            logger.debug(f"Queued '{download['artifact_name']}' for GE rendering.")
            return ImportGcsToArtifactResponse(
                artifact_id=f"{download['artifact_name']}:v{version}",
                gcs_uri=request.gcs_uri,
                content_type=download["mime_type"],
                execution_status="success",
                execution_message=(
                    f"Successfully imported {request.gcs_uri} as artifact "
                    f"'{download['artifact_name']}' (v{version}). "
                    "You can now 'load_artifacts' to process it."
                ),
            ).model_dump()
        except Exception as e:
            logger.error(f"Error importing GCS to artifact: {e}")
            return ImportGcsToArtifactResponse(
                artifact_id="",
                gcs_uri=None,
                execution_status="error",
                execution_message=f"Internal error: {str(e)}",
            ).model_dump()

    def _download_gcs_object(
        self, request: ImportGcsToArtifactRequest
    ) -> dict[str, bytes | str]:
        """Downloads a GCS blob and resolves the artifact name and MIME type.

        Args:
            request: ImportGcsToArtifactRequest -> Validated import request containing the GCS URI.

        Returns:
            dict -> Keys: 'content_bytes' (bytes), 'mime_type' (str), 'artifact_name' (str).
        """
        bucket_name, object_name = request.gcs_uri[5:].split("/", 1)
        artifact_name = request.artifact_name or object_name.split("/")[-1]
        logger.debug(f"Resolved artifact name: {artifact_name}, bucket: {bucket_name}")

        client = storage.Client()
        blob = client.bucket(bucket_name).blob(object_name)

        if not blob.exists():
            raise FileNotFoundError(f"GCS object not found: {request.gcs_uri}")

        mime_type = request.mime_type or blob.content_type
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(artifact_name)
            logger.debug(f"MIME type guessed from extension: {mime_type}")

        return {
            "content_bytes": blob.download_as_bytes(),
            "mime_type": mime_type or "application/octet-stream",
            "artifact_name": artifact_name,
        }

    def _create_artifact_part(
        self, content_bytes: bytes, mime_type: str, artifact_name: str
    ) -> types.Part:
        """Converts raw bytes into the appropriate Gemini Part type based on the MIME type.

        Args:
            content_bytes: bytes -> Raw content of the downloaded GCS object.
            mime_type: str -> MIME type used to select the ingestion strategy.
            artifact_name: str -> Filename used in the fallback placeholder message.

        Returns:
            types.Part -> Gemini-compatible content part ready to be saved as an artifact.
        """
        logger.debug(f"Creating artifact part for MIME type: {mime_type}")

        if mime_type.startswith(_MULTIMODAL_PREFIXES) or mime_type == "application/pdf":
            return types.Part(
                inline_data=types.Blob(data=content_bytes, mime_type=mime_type)
            )

        if mime_type.startswith("text/") or mime_type in _TEXT_LIKE_TYPES:
            text_content = content_bytes.decode("utf-8", errors="replace")
            return types.Part.from_text(text=text_content)

        logger.debug(
            f"Unsupported MIME type '{mime_type}' for '{artifact_name}'; using placeholder."
        )
        return types.Part.from_text(
            text=f"[Binary Artifact: {artifact_name}, type: {mime_type}. Content cannot be displayed inline.]"
        )
