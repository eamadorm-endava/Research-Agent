from datetime import datetime, timezone
from typing import Any, Optional
from loguru import logger
import asyncio
from google.genai import types

from google.adk.plugins.base_plugin import BasePlugin
from google.adk.agents.invocation_context import InvocationContext
from google.adk.tools import ToolContext
from google.adk.tools.base_tool import BaseTool

from .config import METRICS_CONFIG
from .schemas import MetricsRecord, ToolUsageRecord
from .bq_service import MetricsBQService, InsertMetricsRequest


class ResponseTimeMetricsPlugin(BasePlugin):
    """ADK plugin to track and log agent processing and response times to BigQuery.

    Measures initial prompt ingestion, final response generation, and execution times
    for all invoked tools, calculating processing durations in seconds. Writes logs
    asynchronously using the injected MetricsBQService.
    """

    def __init__(self, name: str = "response_time_metrics_plugin"):
        """
        Initializes the metrics plugin and the BigQuery service.

        Args:
            name: str -> The name of the plugin

        Returns:
            None -> No return
        """
        super().__init__(name)
        self._bq_service = MetricsBQService(
            project_id=METRICS_CONFIG.PROJECT_ID,
            dataset_id=METRICS_CONFIG.DATASET_ID,
            table_id=METRICS_CONFIG.TABLE_ID,
        )
        self._active_runs: dict[str, MetricsRecord] = {}
        # Fallback for tool tracking if context store isn't accessible, though we clean it up safely.
        self._active_tools: dict[str, ToolUsageRecord] = {}

    async def before_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> Optional[types.Content]:
        """
        Initializes the execution timing record at the very start of the run.

        Args:
            invocation_context: InvocationContext -> The context of the current agent invocation

        Returns:
            Optional[types.Content] -> Always returns None
        """
        invocation_id = invocation_context.invocation_id
        if invocation_id not in self._active_runs:
            self._active_runs[invocation_id] = MetricsRecord(
                session_id=invocation_context.session.id,
                user_id=invocation_context.user_id,
                prompt_id=invocation_id,
                prompt="",
                initial_time=datetime.now(timezone.utc),
            )
        return None

    async def on_user_message_callback(
        self,
        *,
        invocation_context: InvocationContext,
        user_message: types.Content,
    ) -> Optional[types.Content]:
        """
        Captures the user prompt content and resets the start time for precision.

        Args:
            invocation_context: InvocationContext -> The context of the current agent invocation
            user_message: types.Content -> The message provided by the user

        Returns:
            Optional[types.Content] -> Always returns None
        """
        prompt_text = ""
        if user_message and user_message.parts:
            prompt_text = "".join(part.text for part in user_message.parts if part.text)

        invocation_id = invocation_context.invocation_id
        if invocation_id not in self._active_runs:
            self._active_runs[invocation_id] = MetricsRecord(
                session_id=invocation_context.session.id,
                user_id=invocation_context.user_id,
                prompt_id=invocation_id,
                prompt=prompt_text,
                initial_time=datetime.now(timezone.utc),
            )
        else:
            record: MetricsRecord = self._active_runs[invocation_id]
            record.prompt = prompt_text
            record.initial_time = datetime.now(timezone.utc)
        return None

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict]:
        """
        Records the start timestamp for a tool call.

        Args:
            tool: BaseTool -> The tool being executed
            tool_args: dict[str, Any] -> The arguments passed to the tool
            tool_context: ToolContext -> The context of the tool execution

        Returns:
            Optional[dict] -> Always returns None
        """
        # We use the unique memory address (id) of the tool_context object as the tracking key instead of
        # tool_context.function_call_id. In Gemini, function_call_id is often just the function name (e.g., 'read_file').
        # If the LLM generates multiple concurrent calls to the SAME tool in a single turn, they would all
        # share the same function_call_id and overwrite each other's start times in this dictionary.
        # Since tool_context is a unique object per execution, its id() guarantees safe concurrent tracking.
        self._active_tools[str(id(tool_context))] = ToolUsageRecord(
            tool_name=tool.name, initial_time=datetime.now(timezone.utc)
        )
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
        Calculates and logs tool execution duration on successful complete.

        Args:
            tool: BaseTool -> The tool that was executed
            tool_args: dict[str, Any] -> The arguments passed to the tool
            tool_context: ToolContext -> The context of the tool execution
            result: dict -> The result returned by the tool

        Returns:
            Optional[dict] -> Always returns None
        """
        self._record_tool_completion(tool_context)
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
        Calculates and logs tool execution duration on error.

        Args:
            tool: BaseTool -> The tool that was executed
            tool_args: dict[str, Any] -> The arguments passed to the tool
            tool_context: ToolContext -> The context of the tool execution
            error: Exception -> The error raised by the tool

        Returns:
            Optional[dict] -> Always returns None
        """
        self._record_tool_completion(tool_context)
        return None

    def _record_tool_completion(self, tool_context: ToolContext) -> None:
        """
        Utility to calculate duration and append tool metric records.
        """
        tool_record = self._active_tools.pop(str(id(tool_context)), None)
        if tool_record:
            final_time = datetime.now(timezone.utc)
            tool_record.final_time = final_time
            tool_record.tool_full_time = (
                final_time - tool_record.initial_time
            ).total_seconds()

            # We store the completed tool record back into active_tools so it can be picked up
            # by the after_run_callback or if we somehow pass context around.
            # Wait, no, we need to append it to the current turn's tools_used.
            # But we don't have access to invocation_context here. We can store it in a dict
            # mapped by invocation_id.
            # However, since _active_tools is global, maybe we just use a similar dictionary
            # for completed tools per invocation_id.
            if not hasattr(self, "_completed_tools"):
                self._completed_tools: dict[str, list[ToolUsageRecord]] = {}
            if tool_context.invocation_id not in self._completed_tools:
                self._completed_tools[tool_context.invocation_id] = []
            self._completed_tools[tool_context.invocation_id].append(tool_record)

    async def after_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> None:
        """
        Calculates total turn time, extracts agent response, and writes to BQ.

        Args:
            invocation_context: InvocationContext -> The context of the completed agent invocation

        Returns:
            None -> No return
        """
        record: MetricsRecord | None = self._active_runs.pop(
            invocation_context.invocation_id, None
        )
        if not record:
            return

        final_time = datetime.now(timezone.utc)
        record.final_time = final_time
        record.time_to_answer = (final_time - record.initial_time).total_seconds()
        record.agent_response = self._extract_agent_response(invocation_context)

        # Attach any completed tools
        completed_tools = getattr(self, "_completed_tools", {}).pop(
            invocation_context.invocation_id, []
        )
        record.tools_used = completed_tools

        # Async dispatch to BQ Service (fire and forget to minimize plugin execution time)
        request = InsertMetricsRequest(record=record)

        async def _fire_and_forget_insert() -> None:
            try:
                await self._bq_service.insert_metrics(request)
            except Exception as e:
                logger.error(f"Error calling MetricsBQService: {e}")

        # Keep a strong reference to the background task to prevent garbage collection mid-execution

        if not hasattr(self, "_background_tasks"):
            self._background_tasks = set()
        task = asyncio.create_task(_fire_and_forget_insert())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _extract_agent_response(self, invocation_context: InvocationContext) -> str:
        """
        Extract the text content of the agent's response from session events.

        Args:
            invocation_context: InvocationContext -> The context to extract events from

        Returns:
            str -> The agent response text, or empty string if not found
        """
        agent_response = ""
        try:
            events = invocation_context._get_events(current_invocation=True)
            for event in reversed(events):
                if event.author != "user":
                    if event.content and event.content.parts:
                        text_parts = [
                            part.text for part in event.content.parts if part.text
                        ]
                        if text_parts:
                            agent_response = "".join(text_parts)
                            break
        except Exception as e:
            logger.warning(f"Could not extract agent response from context events: {e}")
        return agent_response
