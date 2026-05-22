import pytest
from unittest.mock import MagicMock, patch
from google.genai import types

from google.adk.tools import ToolContext
from google.adk.tools.base_tool import BaseTool
from agent.core_agent.plugins.metrics.plugin import ResponseTimeMetricsPlugin


@pytest.fixture
def mock_bq_client():
    """Mocks the BigQuery client to avoid real network operations."""
    with patch(
        "agent.core_agent.plugins.metrics.plugin.bigquery.Client"
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.insert_rows_json.return_value = []
        mock_client_cls.return_value = mock_client
        yield mock_client


@pytest.fixture
def metrics_plugin(mock_bq_client):
    """Instantiates the ResponseTimeMetricsPlugin with the mocked BigQuery client."""
    return ResponseTimeMetricsPlugin()


@pytest.mark.asyncio
async def test_metrics_plugin_happy_path(metrics_plugin, mock_bq_client):
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

    # Verify BigQuery insertion
    mock_bq_client.insert_rows_json.assert_called_once()
    args, _ = mock_bq_client.insert_rows_json.call_args
    table_ref, rows = args
    assert table_ref == "ag-core-ops-auj0.agent_metrics.response_times"
    assert len(rows) == 1

    row = rows[0]
    assert row["session_id"] == "test-session-456"
    assert row["user_id"] == "test-user-789"
    assert row["prompt_id"] == "test-invocation-123"
    assert row["prompt"] == "Hello Agent!"
    assert row["agent_response"] == "The current time is 12:00."
    assert row["time_to_answer"] >= 0
    assert len(row["tools_used"]) == 1
    assert row["tools_used"][0]["tool_name"] == "GetCurrentTimeTool"
    assert row["tools_used"][0]["tool_full_time"] >= 0


@pytest.mark.asyncio
async def test_metrics_plugin_tool_error(metrics_plugin, mock_bq_client):
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

    mock_bq_client.insert_rows_json.assert_called_once()
    args, _ = mock_bq_client.insert_rows_json.call_args
    rows = args[1]
    assert len(rows[0]["tools_used"]) == 1
    assert rows[0]["tools_used"][0]["tool_name"] == "ExecuteQueryTool"
    assert rows[0]["tools_used"][0]["tool_full_time"] >= 0


@pytest.mark.asyncio
async def test_metrics_plugin_bigquery_error_caught_silently(
    metrics_plugin, mock_bq_client
):
    """Verifies that failures during BQ insert_rows_json are caught silently and do not break execution."""
    mock_bq_client.insert_rows_json.side_effect = Exception(
        "BigQuery server unavailable"
    )

    mock_invocation_ctx = MagicMock()
    mock_invocation_ctx.invocation_id = "test-invocation-123"
    mock_invocation_ctx.session.id = "test-session-456"
    mock_invocation_ctx.user_id = "test-user-789"

    await metrics_plugin.before_run_callback(invocation_context=mock_invocation_ctx)
    await metrics_plugin.after_run_callback(invocation_context=mock_invocation_ctx)

    # Should not raise exception and execute cleanly
    mock_bq_client.insert_rows_json.assert_called_once()
