from google.adk.tools import BaseTool, ToolContext
from google.genai import types
from typing_extensions import override
from loguru import logger

from .schemas import (
    ImportGcsToArtifactRequest,
    ImportGcsToArtifactResponse,
    GetArtifactUriRequest,
    GetArtifactUriResponse,
)


class GetArtifactUriTool(BaseTool):
    """
    A native ADK tool that retrieves the GCS URI for a session artifact.

    This tool allows the agent to find the canonical storage location (gs://...)
    of any file registered in the current session context.
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
        """
        Returns the tool declaration for Gemini.
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
        """
        Executes the GCS URI retrieval logic.

        Args:
            args: Dictionary containing 'filename' and optional 'version'.
                  May be nested under a 'request' key.
            tool_context: The ADK ToolContext for artifact access.

        Returns:
            Dictionary containing the GetArtifactUriResponse model.
        """
        # Handle potential parameter nesting by Gemini
        if "request" in args and isinstance(args["request"], dict):
            args = args["request"]

        request = GetArtifactUriRequest(**args)
        logger.info(f"Retrieving GCS URI for artifact: {request.filename}")

        try:
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
    """
    A native ADK tool that imports a GCS object into the current session as an artifact.

    This tool bridges external storage and session context by downloading GCS objects
    and re-registering them as native ADK artifacts (inline or text).
    """

    def __init__(self):
        super().__init__(
            name="import_gcs_to_artifact",
            description=(
                "Imports an object from Google Cloud Storage into the current session "
                "as an artifact. Use this when you have a 'gs://' URI (e.g., from "
                "reading a file) and you want to analyze its content (PDF, Image, Video, etc.)."
            ),
        )

    def _get_declaration(self) -> types.FunctionDeclaration | None:
        """
        Returns the tool declaration for Gemini.
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
        """
        Executes the GCS-to-Artifact import logic.

        Args:
            args: Dictionary containing 'gcs_uri', 'artifact_name', and optional 'mime_type'.
                  May be nested under a 'request' key.
            tool_context: The ADK ToolContext for artifact saving.

        Returns:
            Dictionary containing the ImportGcsToArtifactResponse model.
        """
        # Handle potential parameter nesting by Gemini
        if "request" in args and isinstance(args["request"], dict):
            args = args["request"]

        request = ImportGcsToArtifactRequest(**args)
        logger.info(f"Importing GCS object to artifact: {request.gcs_uri}")

        try:
            # 1. Download and determine MIME type
            content_bytes, mime_type, artifact_name = self._download_gcs_object(request)

            # 2. Determine ingestion strategy and create the Part
            artifact_part = self._create_artifact_part(
                content_bytes, mime_type, artifact_name
            )

            # 3. Save as ADK Artifact
            version = await tool_context.save_artifact(
                filename=artifact_name, artifact=artifact_part
            )

            return ImportGcsToArtifactResponse(
                artifact_id=f"{artifact_name}:v{version}",
                gcs_uri=request.gcs_uri,
                content_type=mime_type,
                execution_status="success",
                execution_message=(
                    f"Successfully imported {request.gcs_uri} as artifact '{artifact_name}' (v{version}). "
                    "You can now 'load_artifacts' to process it."
                ),
            ).model_dump()

        except Exception as e:
            logger.error(f"Error importing GCS to artifact: {e}")
            return ImportGcsToArtifactResponse(
                artifact_id="",
                gcs_uri=request.gcs_uri or "",
                execution_status="error",
                execution_message=f"Internal error: {str(e)}",
            ).model_dump()

    def _download_gcs_object(
        self, request: ImportGcsToArtifactRequest
    ) -> tuple[bytes, str, str]:
        """
        Downloads the object from GCS and resolves the artifact name and MIME type.
        """
        if not request.gcs_uri.startswith("gs://"):
            raise ValueError(f"Invalid GCS URI: {request.gcs_uri}")

        uri_parts = request.gcs_uri[5:].split("/", 1)
        if len(uri_parts) < 2:
            raise ValueError(f"Invalid GCS URI: {request.gcs_uri}")
        bucket_name, object_name = uri_parts

        artifact_name = request.artifact_name or object_name.split("/")[-1]

        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)

        if not blob.exists():
            raise FileNotFoundError(f"GCS object not found: {request.gcs_uri}")

        mime_type = request.mime_type or blob.content_type
        if not mime_type:
            import mimetypes

            mime_type, _ = mimetypes.guess_type(artifact_name)

        mime_type = mime_type or "application/octet-stream"
        content_bytes = blob.download_as_bytes()

        return content_bytes, mime_type, artifact_name

    def _create_artifact_part(
        self, content_bytes: bytes, mime_type: str, artifact_name: str
    ) -> types.Part:
        """
        Creates a Gemini-safe Part based on the MIME type.
        """
        multimodal_prefixes = ("image/", "audio/", "video/")
        is_pdf = mime_type == "application/pdf"
        is_text_like = mime_type.startswith("text/") or mime_type in [
            "application/json",
            "application/csv",
            "application/xml",
        ]

        if mime_type.startswith(multimodal_prefixes) or is_pdf:
            return types.Part(
                inline_data=types.Blob(data=content_bytes, mime_type=mime_type)
            )

        if is_text_like:
            try:
                text_content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text_content = content_bytes.decode("utf-8", errors="replace")
            return types.Part.from_text(text=text_content)

        # Unsupported binary fallback
        return types.Part.from_text(
            text=f"[Binary Artifact: {artifact_name}, type: {mime_type}. Content cannot be displayed inline.]"
        )
