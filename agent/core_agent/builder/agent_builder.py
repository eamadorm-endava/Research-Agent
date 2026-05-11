from typing import Callable, Optional, Self, Union

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
    ToolConfig,
    FunctionCallingConfig,
)
from loguru import logger

from ..config import BaseAgentConfig, BaseMCPConfig, GCPConfig, GoogleAuthConfig
from google.adk.tools.skill_toolset import SkillToolset
from ..callbacks.artifact_rendering import render_pending_artifacts
from .mcp_factory import MCPToolsetBuilder
from .skills_factory import get_skill


class AgentBuilder:
    """Orchestrator class to build and configure an ADK Agent application."""

    def __init__(
        self,
        agent_config: BaseAgentConfig,
        gcp_config: GCPConfig,
        auth_config: GoogleAuthConfig,
    ) -> None:
        """Initializes the AgentBuilder, configures the VertexAI client, and sets up the MCP toolset builder.

        Args:
            agent_config: BaseAgentConfig -> Core agent behavioural settings.
            gcp_config: GCPConfig -> Google Cloud Platform project settings.
            auth_config: GoogleAuthConfig -> Shared authentication parameters.
        """
        self.agent_config = agent_config
        self.gcp_config = gcp_config
        self._mcp_builder = MCPToolsetBuilder(auth_config)
        self._registered_tools = []
        self._sub_agents: list[Agent] = []
        self._skills = []
        self._before_callback = None
        self._output_key: Optional[str] = None

        # Initialize VertexAI natively
        vertexai.Client(
            project=self.gcp_config.PROJECT_ID,
            location=self.gcp_config.REGION,
        )
        logger.info(
            f"AgentBuilder initialized VertexAI via {self.gcp_config.PROJECT_ID}/{self.gcp_config.REGION}"
        )

    def with_subagents(self, sub_agents: list[Agent]) -> Self:
        """Registers specialist agents for LLM-transfer delegation via sub_agents= parameter.

        Using sub_agents= (vs. AgentTool) keeps specialists in the same invocation
        context: OAuth challenges, file_data content, and after_agent_callbacks all
        propagate correctly to the user.

        Args:
            sub_agents: list[Agent] -> List of fully configured ADK agents to register.

        Returns:
            Self -> The builder instance for fluent chaining.
        """
        for sub_agent in sub_agents:
            logger.info(f"Registering sub-agent: {sub_agent.name}")
            self._sub_agents.append(sub_agent)
        return self

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
        """Loads and registers ADK skills into a dedicated skills list.

        Args:
            skill_names: list[str] -> Names of the skill directories to load.

        Returns:
            Self -> The builder instance for fluent chaining.
        """
        for name in skill_names:
            logger.info(f"Mounting skill: {name}")
            skill = get_skill(skill_name=name)
            self._skills.append(skill)
        return self

    def with_output_key(self, key: str) -> Self:
        """Persists the agent's final text response to session state under the given key.

        Using output_key gives the sub-agent memory: subsequent turns can read
        the prior result from state, enabling follow-up questions to reference
        earlier research without repeating discovery steps.

        Args:
            key: str -> Session state key under which the agent's output is stored.

        Returns:
            Self -> The builder instance for fluent chaining.
        """
        logger.info(f"Setting output_key: {key}")
        self._output_key = key
        return self

    def with_before_agent_callback(self, callback: Callable) -> Self:
        """Sets the before_agent_callback for the agent.

        Args:
            callback: Callable -> The callback function to run before agent execution.

        Returns:
            Self -> The builder instance for fluent chaining.
        """
        logger.info(f"Registering before_agent_callback: {callback.__name__}")
        self._before_callback = callback
        return self

    def build(self, enable_artifact_rendering: bool = True) -> Agent:
        """Assembles and returns the fully configured ADK Agent from all registered tools and settings.

        Specialists using sub_agents= delegation run in the same invocation context,
        so their after_agent_callbacks and OAuth events propagate correctly to the user.
        Set enable_artifact_rendering=False for all sub-agents — rendering must happen
        only at the root agent level so that PENDING_URI_KEY is cleared in session scope,
        not in a transient sub-agent callback context that may not flush back to the session.

        Args:
            enable_artifact_rendering: bool -> When True (default), registers
                render_pending_artifacts as the after_agent_callback.

        Returns:
            Agent -> The executable agent instance.
        """
        after_callback = render_pending_artifacts if enable_artifact_rendering else None
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
                tool_config=ToolConfig(
                    function_calling_config=FunctionCallingConfig(mode="AUTO")
                ),
            ),
            description=self.agent_config.AGENT_DESCRIPTION or "",
            instruction=self.agent_config.AGENT_INSTRUCTION,
            output_key=self._output_key,
            tools=self._consolidate_tools(),
            sub_agents=self._sub_agents,
            before_agent_callback=self._before_callback,
            after_agent_callback=after_callback,
            planner=BuiltInPlanner(
                thinking_config=ThinkingConfig(
                    thinking_budget=self.agent_config.THINKING_BUDGET,
                    include_thoughts=self.agent_config.INCLUDE_THOUGHTS,
                )
            ),
        )

    def _consolidate_tools(self) -> list:
        """Combines registered tools and skills into a single list for the agent.

        Returns:
            list -> The total tools including MCP, Native, and a single consolidated SkillToolset.
        """
        total_tools = list(self._registered_tools)

        if self._skills:
            # Wrap all skills in one toolset to satisfy Gemini's unique function declaration rules
            total_tools.append(SkillToolset(skills=self._skills))

        return total_tools
