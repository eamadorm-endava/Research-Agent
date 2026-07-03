import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from google.genai import types

from google.adk.tools import ToolContext
from google.adk.tools.base_tool import BaseTool
from agent.core_agent.plugins.metrics.plugin import ResponseTimeMetricsPlugin


@pytest.fixture
def mock_bq_service():
    """Mocks the MetricsBQService to avoid real network operations."""
    with patch("agent.core_agent.plugins.metrics.plugin.MetricsBQService") as mock_cls:
        mock_service = MagicMock()
        mock_service.insert_metrics = AsyncMock()
        mock_cls.return_value = mock_service
        yield mock_service


@pytest.fixture
def metrics_plugin(mock_bq_service):
    """Instantiates the ResponseTimeMetricsPlugin with the mocked BQ service."""
    return ResponseTimeMetricsPlugin()


@pytest.mark.asyncio
async def test_metrics_plugin_happy_path(metrics_plugin, mock_bq_service):
    """Verifies timing tracking and successful metrics collection on standard runner execution."""
    mock_invocation_ctx = MagicMock()
    mock_invocation_ctx.invocation_id = "test-invocation-123"
    mock_invocation_ctx.session.id = "test-session-456"
    mock_invocation_ctx.user_id = "test-user-789"

    # Run before_run
    await metrics_plugin.before_run_callback(invocation_context=mock_invocation_ctx)

    # Receive user message
    user_msg = types.Content(role="user", parts=[types.Part(text="Hello Agent!")])
    await metrics_plugin.on_user_message_callback(
        invocation_context=mock_invocation_ctx, user_message=user_msg
    )

    # Simulate a tool execution
    mock_tool = MagicMock(spec=BaseTool)
    mock_tool.name = "GetCurrentTimeTool"

    mock_tool_ctx = MagicMock(spec=ToolContext)
    mock_tool_ctx.invocation_id = "test-invocation-123"
    mock_tool_ctx.function_call_id = "call-abc"

    await metrics_plugin.before_tool_callback(
        tool=mock_tool, tool_args={}, tool_context=mock_tool_ctx
    )
    await metrics_plugin.after_tool_callback(
        tool=mock_tool,
        tool_args={},
        tool_context=mock_tool_ctx,
        result={"time": "12:00"},
    )

    # Simulate agent response in events history
    mock_event = MagicMock()
    mock_event.author = "core_agent"
    mock_event.content = types.Content(
        role="model", parts=[types.Part(text="The current time is 12:00.")]
    )
    mock_invocation_ctx._get_events.return_value = [mock_event]

    # Run after_run
    await metrics_plugin.after_run_callback(invocation_context=mock_invocation_ctx)

    if (
        hasattr(metrics_plugin, "_background_tasks")
        and metrics_plugin._background_tasks
    ):
        import asyncio

        await asyncio.gather(*metrics_plugin._background_tasks)

    # Verify BigQuery insertion
    mock_bq_service.insert_metrics.assert_called_once()
    request = mock_bq_service.insert_metrics.call_args[0][0]

    record = request.record
    assert record.session_id == "test-session-456"
    assert record.user_id == "test-user-789"
    assert record.prompt_id == "test-invocation-123"
    assert record.prompt == "Hello Agent!"
    assert record.agent_response == "The current time is 12:00."
    assert record.time_to_answer >= 0
    assert len(record.tools_used) == 1
    assert record.tools_used[0].tool_name == "GetCurrentTimeTool"
    assert record.tools_used[0].tool_full_time >= 0


@pytest.mark.asyncio
async def test_metrics_plugin_tool_error(metrics_plugin, mock_bq_service):
    """Ensures tool execution time is tracked correctly even when the tool call fails."""
    mock_invocation_ctx = MagicMock()
    mock_invocation_ctx.invocation_id = "test-invocation-123"
    mock_invocation_ctx.session.id = "test-session-456"
    mock_invocation_ctx.user_id = "test-user-789"

    await metrics_plugin.before_run_callback(invocation_context=mock_invocation_ctx)

    mock_tool = MagicMock(spec=BaseTool)
    mock_tool.name = "ExecuteQueryTool"
    mock_tool_ctx = MagicMock(spec=ToolContext)
    mock_tool_ctx.invocation_id = "test-invocation-123"
    mock_tool_ctx.function_call_id = "call-error"

    await metrics_plugin.before_tool_callback(
        tool=mock_tool, tool_args={}, tool_context=mock_tool_ctx
    )
    await metrics_plugin.on_tool_error_callback(
        tool=mock_tool,
        tool_args={},
        tool_context=mock_tool_ctx,
        error=ValueError("BQ connection dropped"),
    )

    mock_invocation_ctx._get_events.return_value = []
    await metrics_plugin.after_run_callback(invocation_context=mock_invocation_ctx)

    if (
        hasattr(metrics_plugin, "_background_tasks")
        and metrics_plugin._background_tasks
    ):
        import asyncio

        await asyncio.gather(*metrics_plugin._background_tasks)

    mock_bq_service.insert_metrics.assert_called_once()
    request = mock_bq_service.insert_metrics.call_args[0][0]
    record = request.record
    assert len(record.tools_used) == 1
    assert record.tools_used[0].tool_name == "ExecuteQueryTool"
    assert record.tools_used[0].tool_full_time >= 0


@pytest.mark.asyncio
async def test_metrics_plugin_bigquery_error_caught_silently(
    metrics_plugin, mock_bq_service
):
    """Verifies that failures during BQ insert_rows_json are caught silently and do not break execution."""
    mock_bq_service.insert_metrics.side_effect = Exception(
        "BigQuery server unavailable"
    )

    mock_invocation_ctx = MagicMock()
    mock_invocation_ctx.invocation_id = "test-invocation-123"
    mock_invocation_ctx.session.id = "test-session-456"
    mock_invocation_ctx.user_id = "test-user-789"

    await metrics_plugin.before_run_callback(invocation_context=mock_invocation_ctx)
    await metrics_plugin.after_run_callback(invocation_context=mock_invocation_ctx)

    if (
        hasattr(metrics_plugin, "_background_tasks")
        and metrics_plugin._background_tasks
    ):
        import asyncio

        await asyncio.gather(*metrics_plugin._background_tasks)

    # Should not raise exception and execute cleanly
    mock_bq_service.insert_metrics.assert_called_once()
