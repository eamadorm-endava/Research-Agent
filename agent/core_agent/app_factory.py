from typing import Annotated
from vertexai.agent_engines import AdkApp
from google.adk.agents import BaseAgent
from google.adk.artifacts.gcs_artifact_service import GcsArtifactService
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin
from loguru import logger


def create_adk_app(
    agent: Annotated[BaseAgent, "The root ADK agent instance"],
    artifact_bucket: Annotated[str, "GCS bucket name for storing artifacts"],
    app_name: Annotated[str, "The name of the application"] = "research-agent",
) -> AdkApp:
    """Constructs an AdkApp with GCS artifact storage and automatic file capture.

    Args:
        agent: BaseAgent -> The root ADK agent instance.
        artifact_bucket: str -> GCS bucket name for storing artifacts.
        app_name: str -> The name of the application.

    Returns:
        AdkApp -> Configured ADK application instance.
    """
    logger.info(f"Creating AdkApp '{app_name}' with artifact bucket: {artifact_bucket}")

    return AdkApp(
        agent=agent,
        app_name=app_name,
        artifact_service_builder=lambda: GcsArtifactService(
            bucket_name=artifact_bucket
        ),
        plugins=[SaveFilesAsArtifactsPlugin()],
    )
