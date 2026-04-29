from typing import Annotated, Self, Union

from google.adk.agents import BaseAgent
from google.adk.apps.app import App
from google.adk.artifacts.gcs_artifact_service import GcsArtifactService
from google.adk.plugins.base_plugin import BasePlugin
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
        # GE has its own file ingestion pipeline that runs before the agent.
        # Adding any artifact plugin in production causes double-saves and
        # prevents GE from rendering files inline.
        self._registered_plugins = (
            [] if gcp_config.PROD_EXECUTION else [SaveFilesAsArtifactsPlugin()]
        )
        logger.debug(
            f"AppBuilder initialized for agent: {self.agent_config.AGENT_NAME}"
        )

    def with_plugins(self, plugins: list[BasePlugin]) -> Self:
        """Registers additional ADK plugins to the application.

        Args:
            plugins: list[BasePlugin] -> List of plugin instances to add.

        Returns:
            Self -> The builder instance for fluent chaining.
        """
        self._registered_plugins.extend(plugins)
        return self

    def build(self) -> Union[AdkApp, App]:
        """Assembles and returns the application instance (AdkApp for PROD, App for LOCAL).

        Always constructs a base App first, then wraps it in AdkApp for production so
        both environments share an identical agent/plugin configuration.

        Returns:
            Union[AdkApp, App] -> The configured application instance ready to be served.

        Raises:
            ValueError: If required production configuration is missing.
        """
        base_application = App(
            name=self.agent_config.AGENT_NAME,
            root_agent=self.agent,
            plugins=self._registered_plugins,
        )

        if self.gcp_config.PROD_EXECUTION:
            if not self.gcp_config.ARTIFACT_BUCKET:
                logger.error("ARTIFACT_BUCKET is required for production execution")
                raise ValueError(
                    "ARTIFACT_BUCKET must be set when PROD_EXECUTION is True"
                )

            logger.info(
                f"Building AdkApp (Production) for '{self.agent_config.AGENT_NAME}' "
                f"in {self.gcp_config.REGION} with bucket: {self.gcp_config.ARTIFACT_BUCKET}"
            )
            return AdkApp(
                app=base_application,
                artifact_service_builder=lambda: GcsArtifactService(
                    bucket_name=self.gcp_config.ARTIFACT_BUCKET
                ),
            )

        logger.info(
            f"Building App (Local) for '{self.agent_config.AGENT_NAME}'. "
            f"GCS artifact storage is provided via --artifact_service_uri at startup."
        )
        return base_application
