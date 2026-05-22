from datetime import datetime, timezone
from typing import Any, Optional
from loguru import logger
from google.cloud import bigquery
from google.genai import types

from google.adk.plugins.base_plugin import BasePlugin
from google.adk.agents.invocation_context import InvocationContext
from google.adk.tools import ToolContext
from google.adk.tools.base_tool import BaseTool

from .config import METRICS_CONFIG
from .schemas import MetricsRecord, ToolUsageRecord


class ResponseTimeMetricsPlugin(BasePlugin):
    """ADK plugin to track and log agent processing and response times to BigQuery.

    Measures initial prompt ingestion, final response generation, and execution times
    for all invoked tools, calculating processing durations in seconds. Writes logs
    asynchronously/synchronously to a BigQuery table using the streaming buffer.
    """

    def __init__(self, name: str = "response_time_metrics_plugin"):
        """
        Initializes the metrics plugin and the BigQuery client.

        Args:
            name: str -> The name of the plugin

        Returns:
            None -> No return
        """
        super().__init__(name)
        self.project_id = METRICS_CONFIG.project_id
        self.dataset_id = METRICS_CONFIG.dataset_id
        self.table_id = METRICS_CONFIG.table_id
        self.table_ref = f"{self.project_id}.{self.dataset_id}.{self.table_id}"
        self._client = None
        self._runs: dict[str, dict] = {}
        self._active_tools: dict[str, dict] = {}

    @property
    def client(self) -> bigquery.Client:
        """
        Lazily instantiates the BigQuery client to avoid authentication checks at init time.

        Returns:
            bigquery.Client -> The initialized BigQuery client
        """
        if self._client is None:
            self._client = bigquery.Client()
        return self._client

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
        prompt_id = invocation_context.invocation_id
        if prompt_id not in self._runs:
            self._runs[prompt_id] = {
                "session_id": invocation_context.session.id,
                "user_id": invocation_context.user_id,
                "prompt_id": prompt_id,
                "prompt": "",
                "initial_time": datetime.now(timezone.utc),
                "tools_used": [],
            }
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
        prompt_id = invocation_context.invocation_id
        prompt_text = ""
        if user_message and user_message.parts:
            prompt_text = "".join(part.text for part in user_message.parts if part.text)

        if prompt_id not in self._runs:
            self._runs[prompt_id] = {
                "session_id": invocation_context.session.id,
                "user_id": invocation_context.user_id,
                "prompt_id": prompt_id,
                "prompt": prompt_text,
                "initial_time": datetime.now(timezone.utc),
                "tools_used": [],
            }
        else:
            self._runs[prompt_id]["prompt"] = prompt_text
            self._runs[prompt_id]["initial_time"] = datetime.now(timezone.utc)
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
        self._active_tools[tool_context.function_call_id] = {
            "tool_name": tool.name,
            "initial_time": datetime.now(timezone.utc),
        }
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

        Args:
            tool_context: ToolContext -> The context of the tool execution

        Returns:
            None -> No return
        """
        tool_info = self._active_tools.pop(tool_context.function_call_id, None)
        if tool_info:
            final_time = datetime.now(timezone.utc)
            tool_info["final_time"] = final_time
            tool_info["tool_full_time"] = (
                final_time - tool_info["initial_time"]
            ).total_seconds()

            run_id = tool_context.invocation_id
            if run_id in self._runs:
                self._runs[run_id]["tools_used"].append(tool_info)

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
        prompt_id = invocation_context.invocation_id
        run_info = self._runs.pop(prompt_id, None)
        if not run_info:
            return

        final_time = datetime.now(timezone.utc)
        time_to_answer = (final_time - run_info["initial_time"]).total_seconds()

        # Extract the text content of the agent's response from session events
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

        # Assemble and write the row data to BigQuery
        try:
            tools_used_records = [
                ToolUsageRecord(
                    tool_name=t["tool_name"],
                    initial_time=t["initial_time"],
                    final_time=t["final_time"],
                    tool_full_time=t["tool_full_time"],
                )
                for t in run_info["tools_used"]
            ]

            record = MetricsRecord(
                session_id=run_info["session_id"],
                user_id=run_info["user_id"],
                prompt_id=run_info["prompt_id"],
                prompt=run_info["prompt"],
                agent_response=agent_response,
                initial_time=run_info["initial_time"],
                final_time=final_time,
                time_to_answer=time_to_answer,
                tools_used=tools_used_records,
            )

            row_data = record.model_dump(mode="json")
            errors = self.client.insert_rows_json(self.table_ref, [row_data])
            if errors:
                logger.error(
                    f"Failed to insert response time metrics to BigQuery: {errors}"
                )
            else:
                logger.info(
                    f"Successfully logged response time metrics to BigQuery for session {record.session_id}"
                )

        except Exception as e:
            logger.error(f"Error logging metrics to BigQuery: {e}")
