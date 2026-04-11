from typing import Self
from loguru import logger
import vertexai
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.planners import BuiltInPlanner
from google.genai.types import (
    GenerateContentConfig,
    HttpRetryOptions,
    ThinkingConfig,
)

from ..config import AgentConfig, BaseMCPConfig, GCPConfig, GoogleAuthConfig
from .mcp_factory import MCPToolsetBuilder
from .skills_factory import get_skill_toolset


class AgentBuilder:
    """Orchestrator class to build and configure an ADK Agent application."""

    def __init__(
        self,
        agent_config: AgentConfig,
        gcp_config: GCPConfig,
        auth_config: GoogleAuthConfig,
    ) -> None:
        """Initializes the AgentBuilder with necessary configurations.
        Sets up the GCP environment and the internal MCP toolset builder.

        Args:
            agent_config (AgentConfig): Core agent behavioral settings.
            gcp_config (GCPConfig): Google Cloud Platform project settings.
            auth_config (GoogleAuthConfig): Shared authentication parameters.

        Returns:
            None
        """
        self.agent_config = agent_config
        self.gcp_config = gcp_config
        self._mcp_builder = MCPToolsetBuilder(auth_config)
        self._tools = []

        # Initialize VertexAI natively
        vertexai.Client(
            project=self.gcp_config.PROJECT_ID,
            location=self.gcp_config.REGION,
        )
        logger.info(
            f"AgentBuilder initialized VertexAI via {self.gcp_config.PROJECT_ID}/{self.gcp_config.REGION}"
        )

    def with_mcp_servers(self, mcp_configs: list[BaseMCPConfig]) -> Self:
        """Registers multiple MCP servers to the agent's toolset.
        Uses the internal builder to construct validated ADK toolsets.

        Args:
            mcp_configs (list[BaseMCPConfig]): List of MCP server configurations.

        Returns:
            Self: The builder instance for fluent chaining.
        """
        for config in mcp_configs:
            mcp_toolset = self._mcp_builder.build(
                mcp_config=config,
                prod_execution=self.gcp_config.PROD_EXECUTION,
            )
            self._tools.append(mcp_toolset)
        return self

    def with_skills(self, skill_names: list[str]) -> Self:
        """Adds business logic skills to the agent by their component names.
        Loads skill toolsets from the predefined agent skills directory.

        Args:
            skill_names (list[str]): Names of the skills to mount. Its the name of the folder in the skills directory.

        Returns:
            Self: The builder instance for fluent chaining.
        """
        for name in skill_names:
            skill_toolset = get_skill_toolset(skill_name=name)
            self._tools.append(skill_toolset)
        return self

    def _build_agent_settings(self) -> GenerateContentConfig:
        """Constructs the generative model configuration for the agent.
        Maps internal pydantic settings to the Google GenAI schema.

        Returns:
            GenerateContentConfig: Validated model configuration.
        """
        return GenerateContentConfig(
            temperature=self.agent_config.TEMPERATURE,
            top_p=self.agent_config.TOP_P,
            top_k=self.agent_config.TOP_K,
            max_output_tokens=self.agent_config.MAX_OUTPUT_TOKENS,
            seed=self.agent_config.SEED,
        )

    def _build_retry_options(self) -> HttpRetryOptions:
        """Constructs the HTTP retry strategy for model interactions.
        Defines attempts and backoff parameters from agent settings.

        Returns:
            HttpRetryOptions: Configured retry logic for the Gemini model.
        """
        return HttpRetryOptions(
            attempts=self.agent_config.RETRY_ATTEMPTS,
            initial_delay=self.agent_config.RETRY_INITIAL_DELAY,
            exp_base=self.agent_config.RETRY_EXP_BASE,
            max_delay=self.agent_config.RETRY_MAX_DELAY,
        )

    def _build_planner(self) -> BuiltInPlanner:
        """Initializes the agent's reasoning planner with thinking configurations.
        Configures the thinking budget and thought tracking behavior.

        Returns:
            BuiltInPlanner: The reasoning core for the agent.
        """
        return BuiltInPlanner(
            thinking_config=ThinkingConfig(
                thinking_budget=self.agent_config.THINKING_BUDGET,
                include_thoughts=self.agent_config.INCLUDE_THOUGHTS,
            )
        )

    def build(self) -> Agent:
        """
        Assembles the agent instance that will be used in the application.
        Returns:
            Agent: The executable agent instance.
        """
        root_agent = Agent(
            model=Gemini(
                model_name=self.agent_config.MODEL_NAME,
                retry_options=self._build_retry_options(),
            ),
            name=self.agent_config.AGENT_NAME,
            generate_content_config=self._build_agent_settings(),
            instruction=self.agent_config.AGENT_INSTRUCTION,
            tools=self._tools,
            planner=self._build_planner(),
        )

        return root_agent
