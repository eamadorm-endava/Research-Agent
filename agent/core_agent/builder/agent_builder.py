from typing import Callable, Self, Union

import vertexai
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.planners import BuiltInPlanner
from google.adk.tools import BaseTool, FunctionTool
from google.genai.types import (
    GenerateContentConfig,
    HttpRetryOptions,
    ModelArmorConfig,
    ThinkingConfig,
)
from loguru import logger

from ..config import AgentConfig, BaseMCPConfig, GCPConfig, GoogleAuthConfig
from ..callbacks.artifact_rendering import render_pending_artifacts
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
        """Initializes the AgentBuilder, configures the VertexAI client, and sets up the MCP toolset builder.

        Args:
            agent_config: AgentConfig -> Core agent behavioural settings.
            gcp_config: GCPConfig -> Google Cloud Platform project settings.
            auth_config: GoogleAuthConfig -> Shared authentication parameters.
        """
        self.agent_config = agent_config
        self.gcp_config = gcp_config
        self._mcp_builder = MCPToolsetBuilder(auth_config)
        self._registered_tools = []

        # Initialize VertexAI natively
        vertexai.Client(
            project=self.gcp_config.PROJECT_ID,
            location=self.gcp_config.REGION,
        )
        logger.info(
            f"AgentBuilder initialized VertexAI via {self.gcp_config.PROJECT_ID}/{self.gcp_config.REGION}"
        )

    def with_mcp_servers(self, mcp_configs: list[BaseMCPConfig]) -> Self:
        """Registers multiple MCP servers to the agent's toolset via the internal MCPToolsetBuilder.

        Args:
            mcp_configs: list[BaseMCPConfig] -> List of MCP server configurations to mount.

        Returns:
            Self -> The builder instance for fluent chaining.
        """
        for config in mcp_configs:
            mcp_toolset = self._mcp_builder.build(
                mcp_config=config,
                prod_execution=self.gcp_config.PROD_EXECUTION,
            )
            self._registered_tools.append(mcp_toolset)
        return self

    def with_native_tools(self, native_tools: list[Union[BaseTool, Callable]]) -> Self:
        """Registers native ADK tools or callables to the agent, wrapping plain functions in FunctionTool.

        Args:
            native_tools: list[Union[BaseTool, Callable]] -> List of tools or callables to add.

        Returns:
            Self -> The builder instance for fluent chaining.
        """
        for tool in native_tools:
            if not isinstance(tool, BaseTool):
                tool = FunctionTool(fn=tool)
            self._registered_tools.append(tool)
        return self

    def with_skills(self, skill_names: list[str]) -> Self:
        """Loads and registers ADK skill toolsets from the agent/skills/ directory by folder name.

        Args:
            skill_names: list[str] -> Names of the skill directories to load.

        Returns:
            Self -> The builder instance for fluent chaining.
        """
        for name in skill_names:
            skill_toolset = get_skill_toolset(skill_name=name)
            self._registered_tools.append(skill_toolset)
        return self

    def build(self) -> Agent:
        """Assembles and returns the fully configured ADK Agent from all registered tools and settings.

        Returns:
            Agent -> The executable agent instance.
        """
        return Agent(
            model=Gemini(
                model_name=self.agent_config.MODEL_NAME,
                retry_options=HttpRetryOptions(
                    attempts=self.agent_config.RETRY_ATTEMPTS,
                    initial_delay=self.agent_config.RETRY_INITIAL_DELAY,
                    exp_base=self.agent_config.RETRY_EXP_BASE,
                    max_delay=self.agent_config.RETRY_MAX_DELAY,
                ),
            ),
            name=self.agent_config.AGENT_NAME,
            generate_content_config=GenerateContentConfig(
                temperature=self.agent_config.TEMPERATURE,
                top_p=self.agent_config.TOP_P,
                top_k=self.agent_config.TOP_K,
                max_output_tokens=self.agent_config.MAX_OUTPUT_TOKENS,
                seed=self.agent_config.SEED,
                model_armor_config=ModelArmorConfig(
                    prompt_template_name=(
                        f"projects/{self.gcp_config.PROJECT_ID}/locations/"
                        f"{self.gcp_config.REGION}/templates/"
                        f"{self.agent_config.MODEL_ARMOR_TEMPLATE_ID}"
                    ),
                    response_template_name=(
                        f"projects/{self.gcp_config.PROJECT_ID}/locations/"
                        f"{self.gcp_config.REGION}/templates/"
                        f"{self.agent_config.MODEL_ARMOR_TEMPLATE_ID}"
                    ),
                )
                if self.agent_config.MODEL_ARMOR_TEMPLATE_ID
                else None,
            ),
            instruction=self.agent_config.AGENT_INSTRUCTION,
            tools=self._registered_tools,
            after_agent_callback=render_pending_artifacts,
            planner=BuiltInPlanner(
                thinking_config=ThinkingConfig(
                    thinking_budget=self.agent_config.THINKING_BUDGET,
                    include_thoughts=self.agent_config.INCLUDE_THOUGHTS,
                )
            ),
        )
