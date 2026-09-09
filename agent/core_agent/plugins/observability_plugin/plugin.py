import time
from typing import Any, Optional
from loguru import logger
from opentelemetry.trace import get_current_span
from opentelemetry.semconv._incubating.attributes import gen_ai_attributes
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.adk.telemetry._metrics import (
    record_agent_invocation_duration,
    record_tool_execution_duration,
    record_client_operation_duration,
    record_client_token_usage,
)
from .metrics import (
    agent_invocation_requests,
    agent_invocation_errors,
    tool_execution_requests,
    tool_execution_errors,
)


class ObservabilityPlugin(BasePlugin):
    """
    Plugin for comprehensive observability across Google ADK agent lifecycle.
    Captures OpenTelemetry traces, structured Loguru logs, and emits GenAI metrics.
    """

    def __init__(self, name: str = "observability_plugin") -> None:
        """
        Initializes the ObservabilityPlugin with state tracking for durations.

        Args:
            name: str -> Unique identifier name for the plugin instance.

        Returns:
            None
        """
        super().__init__(name=name)
        self._turn_start_times: dict[str, float] = {}
        self._model_start_times: dict[str, float] = {}
        self._active_llm_requests: dict[str, LlmRequest] = {}
        self._tool_start_times: dict[tuple[int, str], float] = {}

    async def before_run_callback(
        self,
        *,
        invocation_context: InvocationContext,
        **kwargs: Any,
    ) -> None:
        """
        Injects context into the active trace span, binds Loguru, and starts timing.

        Args:
            invocation_context: InvocationContext -> Current run execution context.

        Returns:
            None
        """
        try:
            session_id = invocation_context.session.id
            user_id = invocation_context.user_id

            current_span = get_current_span()
            if current_span.is_recording():
                current_span.set_attribute("session_id", session_id)
                if user_id:
                    current_span.set_attribute("user_id", user_id)

            logger.configure(extra={"session_id": session_id, "user_id": user_id})
            logger.info(f"Agent Turn started for Session ID: {session_id}")

            agent_name = (
                invocation_context.agent.name
                if invocation_context.agent
                else "unknown_agent"
            )
            self._turn_start_times[invocation_context.invocation_id] = (
                time.perf_counter()
            )
            agent_invocation_requests.add(
                1, {gen_ai_attributes.GEN_AI_AGENT_NAME: agent_name}
            )
        except Exception as exc:
            logger.warning(f"ObservabilityPlugin before_run_callback error: {exc}")

    async def after_run_callback(
        self,
        *,
        invocation_context: InvocationContext,
        **kwargs: Any,
    ) -> None:
        """
        Calculates turn duration and records agent invocation metrics.

        Args:
            invocation_context: InvocationContext -> Current run execution context.

        Returns:
            None
        """
        try:
            start_time = self._turn_start_times.pop(
                invocation_context.invocation_id, None
            )
            if start_time is None:
                return

            elapsed_s = time.perf_counter() - start_time
            agent_name = (
                invocation_context.agent.name
                if invocation_context.agent
                else "unknown_agent"
            )
            record_agent_invocation_duration(agent_name=agent_name, elapsed_s=elapsed_s)
            logger.info(
                f"Agent Turn completed in {elapsed_s:.3f}s for Session ID: "
                f"{invocation_context.session.id}"
            )
        except Exception as exc:
            logger.warning(f"ObservabilityPlugin after_run_callback error: {exc}")

    async def before_model_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_request: LlmRequest,
    ) -> Optional[LlmResponse]:
        """
        Records model start timestamp and caches active request metadata.

        Args:
            callback_context: CallbackContext -> Current agent execution context.
            llm_request: LlmRequest -> Prepared request sent to LLM.

        Returns:
            Optional[LlmResponse] -> None to proceed with model invocation.
        """
        try:
            inv_id = callback_context.invocation_id
            self._model_start_times[inv_id] = time.perf_counter()
            self._active_llm_requests[inv_id] = llm_request
        except Exception as exc:
            logger.warning(f"ObservabilityPlugin before_model_callback error: {exc}")
        return None

    async def after_model_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_response: LlmResponse,
    ) -> Optional[LlmResponse]:
        """
        Records LLM operation latency and token usage from response metadata.

        Args:
            callback_context: CallbackContext -> Current agent execution context.
            llm_response: LlmResponse -> Model response returned by LLM.

        Returns:
            Optional[LlmResponse] -> None to proceed with unmodified response.
        """
        try:
            inv_id = callback_context.invocation_id
            start_time = self._model_start_times.pop(inv_id, None)
            fallback_model = getattr(llm_response, "model_version", "gemini-2.5-flash")
            llm_request = self._active_llm_requests.pop(
                inv_id,
                LlmRequest(model=fallback_model),
            )

            agent_name = callback_context.agent_name
            if start_time is not None:
                elapsed_s = time.perf_counter() - start_time
                record_client_operation_duration(
                    agent_name=agent_name,
                    elapsed_s=elapsed_s,
                    llm_request=llm_request,
                    responses=[llm_response],
                )

            record_client_token_usage(
                agent_name=agent_name,
                llm_request=llm_request,
                responses=[llm_response],
            )
        except Exception as exc:
            logger.warning(f"ObservabilityPlugin after_model_callback error: {exc}")
        return None

    async def on_model_error_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_request: LlmRequest,
        error: Exception,
    ) -> Optional[LlmResponse]:
        """
        Records model error metrics and failed operation latency.

        Args:
            callback_context: CallbackContext -> Current agent execution context.
            llm_request: LlmRequest -> Prepared request sent to LLM.
            error: Exception -> Exception encountered during generation.

        Returns:
            Optional[LlmResponse] -> None to propagate original error.
        """
        try:
            inv_id = callback_context.invocation_id
            start_time = self._model_start_times.pop(inv_id, None)
            self._active_llm_requests.pop(inv_id, None)

            agent_name = callback_context.agent_name
            elapsed_s = time.perf_counter() - start_time if start_time else 0.0
            record_client_operation_duration(
                agent_name=agent_name,
                elapsed_s=elapsed_s,
                llm_request=llm_request,
                responses=[],
                error=error,
            )
            agent_invocation_errors.add(
                1,
                {
                    gen_ai_attributes.GEN_AI_AGENT_NAME: agent_name,
                    "error.type": type(error).__name__,
                },
            )
        except Exception as exc:
            logger.warning(f"ObservabilityPlugin on_model_error_callback error: {exc}")
        return None

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict]:
        """
        Records tool execution start timestamp and increments invocation counter.

        Args:
            tool: BaseTool -> Tool instance about to be executed.
            tool_args: dict[str, Any] -> Arguments passed to the tool.
            tool_context: ToolContext -> Context specific to tool execution.

        Returns:
            Optional[dict] -> None to proceed with unmodified arguments.
        """
        try:
            key = (id(tool_context), tool.name)
            self._tool_start_times[key] = time.perf_counter()
            agent_name = getattr(tool_context, "agent_name", "unknown_agent")
            tool_execution_requests.add(
                1,
                {
                    "gen_ai.tool.name": tool.name,
                    gen_ai_attributes.GEN_AI_AGENT_NAME: agent_name,
                },
            )
        except Exception as exc:
            logger.warning(f"ObservabilityPlugin before_tool_callback error: {exc}")
        return None

    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict,
    ) -> Optional[dict]:
        """
        Calculates tool duration and records tool execution metrics.

        Args:
            tool: BaseTool -> Tool instance that was executed.
            tool_args: dict[str, Any] -> Arguments passed to the tool.
            tool_context: ToolContext -> Context specific to tool execution.
            result: dict -> Result returned by tool execution.

        Returns:
            Optional[dict] -> None to retain original result.
        """
        try:
            key = (id(tool_context), tool.name)
            start_time = self._tool_start_times.pop(key, None)
            if start_time is not None:
                elapsed_s = time.perf_counter() - start_time
                agent_name = getattr(tool_context, "agent_name", "unknown_agent")
                record_tool_execution_duration(
                    tool_name=tool.name,
                    agent_name=agent_name,
                    elapsed_s=elapsed_s,
                )
        except Exception as exc:
            logger.warning(f"ObservabilityPlugin after_tool_callback error: {exc}")
        return None

    async def on_tool_error_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        error: Exception,
    ) -> Optional[dict]:
        """
        Records tool execution failure metrics and elapsed error duration.

        Args:
            tool: BaseTool -> Tool instance that encountered error.
            tool_args: dict[str, Any] -> Arguments passed to the tool.
            tool_context: ToolContext -> Context specific to tool execution.
            error: Exception -> Exception raised during execution.

        Returns:
            Optional[dict] -> None to propagate original error.
        """
        try:
            key = (id(tool_context), tool.name)
            start_time = self._tool_start_times.pop(key, None)
            elapsed_s = time.perf_counter() - start_time if start_time else 0.0
            agent_name = getattr(tool_context, "agent_name", "unknown_agent")
            record_tool_execution_duration(
                tool_name=tool.name,
                agent_name=agent_name,
                elapsed_s=elapsed_s,
                error=error,
            )
            tool_execution_errors.add(
                1,
                {
                    "gen_ai.tool.name": tool.name,
                    gen_ai_attributes.GEN_AI_AGENT_NAME: agent_name,
                    "error.type": type(error).__name__,
                },
            )
        except Exception as exc:
            logger.warning(f"ObservabilityPlugin on_tool_error_callback error: {exc}")
        return None
