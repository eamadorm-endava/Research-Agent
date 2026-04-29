from typing import Annotated, Any, Self

from google.adk.agents import BaseAgent
from google.adk.apps.app import App
from google.adk.artifacts.gcs_artifact_service import GcsArtifactService
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin
from loguru import logger
from vertexai.agent_engines import AdkApp

from ..config import AgentConfig, GCPConfig


class AppBuilder:
    """Orchestrator class to build and configure the ADK Application (Local or Production)."""

    def __init__(
        self,
        agent: Annotated[BaseAgent, "The root ADK agent instance"],
        gcp_config: GCPConfig,
        agent_config: AgentConfig,
    ) -> None:
        """Initializes the AppBuilder with required configurations and the root agent.

        Args:
            agent: BaseAgent -> The root ADK agent instance.
            gcp_config: GCPConfig -> Google Cloud Platform project settings.
            agent_config: AgentConfig -> Core agent and application settings.
        """
        self.agent = agent
        self.gcp_config = gcp_config
        self.agent_config = agent_config
        self._plugins = [SaveFilesAsArtifactsPlugin()]
        logger.debug(
            f"AppBuilder initialized for agent: {self.agent_config.AGENT_NAME}"
        )

    def with_plugins(self, plugins: list[Any]) -> Self:
        """Registers additional ADK plugins to the application.

        Args:
            plugins: list[Any] -> List of plugin instances to add.

        Returns:
            Self -> The builder instance for fluent chaining.
        """
        self._plugins.extend(plugins)
        return self

    def build(self) -> AdkApp | App:
        """Assembles and returns the application instance (AdkApp for PROD, App for LOCAL).

        Returns:
            AdkApp | App -> The configured application instance ready to be served.
        """
        if self.gcp_config.PROD_EXECUTION:
            logger.info(
                f"Building AdkApp (Production) for '{self.agent_config.AGENT_NAME}' "
                f"in {self.gcp_config.REGION} with bucket: {self.gcp_config.ARTIFACT_BUCKET}"
            )
            return AdkApp(
                agent=self.agent,
                app_name=self.agent_config.AGENT_NAME,
                artifact_service_builder=lambda: GcsArtifactService(
                    bucket_name=self.gcp_config.ARTIFACT_BUCKET
                ),
                plugins=self._plugins,
                enable_tracing=self.agent_config.ENABLE_TRACING,
            )

        logger.info(
            f"Building App (Local) for '{self.agent_config.AGENT_NAME}' with {len(self._plugins)} plugins"
        )
        return App(
            name=self.agent_config.AGENT_NAME,
            root_agent=self.agent,
            plugins=self._plugins,
        )
