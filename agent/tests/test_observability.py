from unittest.mock import MagicMock, patch
import pytest
from google.genai import types
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from agent.core_agent.observability import setup_observability
from agent.core_agent.plugins.observability_plugin.plugin import ObservabilityPlugin


# ─── Setup Observability Tests ───────────────────────────────────────────────


@patch("agent.core_agent.observability.google.cloud.logging.Client")
@patch("agent.core_agent.observability.maybe_set_otel_providers")
@patch("agent.core_agent.observability.get_gcp_exporters")
@patch("agent.core_agent.observability.metrics.get_meter_provider")
def test_SetupObservability_ShouldConfigureLoggingAndMetrics_WhenInvoked(
    mock_get_meter_provider,
    mock_get_gcp_exporters,
    mock_maybe_set_otel_providers,
    mock_logging_client,
):
    mock_get_meter_provider.return_value = MagicMock(spec=[])
    mock_get_gcp_exporters.return_value = MagicMock()

    setup_observability(project_id="test-project")

    mock_logging_client.assert_called_once()
    mock_get_gcp_exporters.assert_called_once_with(
        enable_cloud_tracing=True,
        enable_cloud_metrics=True,
        enable_cloud_logging=False,
    )
    mock_maybe_set_otel_providers.assert_called_once()


@patch("agent.core_agent.observability.google.cloud.logging.Client")
@patch("agent.core_agent.observability.get_gcp_exporters")
@patch("agent.core_agent.observability.metrics.get_meter_provider")
def test_SetupObservability_ShouldBeIdempotent_WhenMeterProviderAlreadySet(
    mock_get_meter_provider,
    mock_get_gcp_exporters,
    mock_logging_client,
):
    from opentelemetry.sdk.metrics import MeterProvider

    mock_get_meter_provider.return_value = MagicMock(spec=MeterProvider)

    setup_observability(project_id="test-project")

    mock_get_gcp_exporters.assert_not_called()


@patch("agent.core_agent.observability.google.cloud.logging.Client")
@patch("agent.core_agent.observability.get_gcp_exporters")
@patch("agent.core_agent.observability.metrics.get_meter_provider")
def test_SetupObservability_ShouldHandleMissingCredentialsGracefully_WhenGcpFails(
    mock_get_meter_provider,
    mock_get_gcp_exporters,
    mock_logging_client,
):
    mock_get_meter_provider.return_value = MagicMock(spec=[])
    mock_logging_client.side_effect = Exception("ADC not found")
    mock_get_gcp_exporters.side_effect = Exception("No credentials found")

    # Should not raise exception
    setup_observability(project_id="test-project")


# ─── ObservabilityPlugin Run Lifecycle Tests ─────────────────────────────────


@pytest.mark.asyncio
@patch("agent.core_agent.plugins.observability_plugin.plugin.get_current_span")
@patch("agent.core_agent.plugins.observability_plugin.plugin.agent_invocation_requests")
async def test_BeforeRun_ShouldSetSpanAttributesAndIncrementRequestCount_WhenTurnStarts(
    mock_agent_requests,
    mock_get_span,
):
    mock_span = MagicMock()
    mock_span.is_recording.return_value = True
    mock_get_span.return_value = mock_span

    plugin = ObservabilityPlugin()
    mock_ctx = MagicMock()
    mock_ctx.session.id = "session-123"
    mock_ctx.user_id = "user-456"
    mock_ctx.agent.name = "coordinator_agent"
    mock_ctx.invocation_id = "inv-789"

    await plugin.before_run_callback(invocation_context=mock_ctx)

    mock_span.set_attribute.assert_any_call("session_id", "session-123")
    mock_span.set_attribute.assert_any_call("user_id", "user-456")
    mock_agent_requests.add.assert_called_once_with(
        1, {"gen_ai.agent.name": "coordinator_agent"}
    )
    assert "inv-789" in plugin._turn_start_times


@pytest.mark.asyncio
@patch(
    "agent.core_agent.plugins.observability_plugin.plugin.record_agent_invocation_duration"
)
async def test_AfterRun_ShouldRecordTurnDuration_WhenTurnCompletes(
    mock_record_duration,
):
    plugin = ObservabilityPlugin()
    plugin._turn_start_times["inv-789"] = 100.0

    mock_ctx = MagicMock()
    mock_ctx.session.id = "session-123"
    mock_ctx.agent.name = "coordinator_agent"
    mock_ctx.invocation_id = "inv-789"

    with patch("time.perf_counter", return_value=102.5):
        await plugin.after_run_callback(invocation_context=mock_ctx)

    mock_record_duration.assert_called_once_with(
        agent_name="coordinator_agent",
        elapsed_s=2.5,
    )
    assert "inv-789" not in plugin._turn_start_times


@pytest.mark.asyncio
@patch(
    "agent.core_agent.plugins.observability_plugin.plugin.record_agent_invocation_duration"
)
async def test_AfterRun_ShouldNotCrash_WhenTurnCompletesWithoutBeforeRun(
    mock_record_duration,
):
    plugin = ObservabilityPlugin()
    mock_ctx = MagicMock()
    mock_ctx.invocation_id = "untracked-inv"

    await plugin.after_run_callback(invocation_context=mock_ctx)
    mock_record_duration.assert_not_called()


# ─── ObservabilityPlugin Model Lifecycle Tests ───────────────────────────────


@pytest.mark.asyncio
@patch("agent.core_agent.plugins.observability_plugin.plugin.record_client_token_usage")
@patch(
    "agent.core_agent.plugins.observability_plugin.plugin.record_client_operation_duration"
)
async def test_AfterModel_ShouldRecordTokenUsageAndDuration_WhenModelCallSucceeds(
    mock_record_duration,
    mock_record_tokens,
):
    plugin = ObservabilityPlugin()
    mock_callback_ctx = MagicMock()
    mock_callback_ctx.invocation_id = "inv-model-1"
    mock_callback_ctx.agent_name = "research_agent"

    llm_req = LlmRequest(model="gemini-2.5-flash")

    # 1. Before model call
    with patch("time.perf_counter", return_value=10.0):
        await plugin.before_model_callback(
            callback_context=mock_callback_ctx,
            llm_request=llm_req,
        )

    # 2. After model call
    usage = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=150,
        candidates_token_count=50,
        total_token_count=200,
    )
    llm_resp = LlmResponse(
        content=types.Content(parts=[types.Part(text="Response")]),
        usage_metadata=usage,
        model_version="gemini-2.5-flash",
    )

    with patch("time.perf_counter", return_value=11.2):
        await plugin.after_model_callback(
            callback_context=mock_callback_ctx,
            llm_response=llm_resp,
        )

    mock_record_duration.assert_called_once_with(
        agent_name="research_agent",
        elapsed_s=pytest.approx(1.2),
        llm_request=llm_req,
        responses=[llm_resp],
    )
    mock_record_tokens.assert_called_once_with(
        agent_name="research_agent",
        llm_request=llm_req,
        responses=[llm_resp],
    )


@pytest.mark.asyncio
@patch("agent.core_agent.plugins.observability_plugin.plugin.record_client_token_usage")
@patch(
    "agent.core_agent.plugins.observability_plugin.plugin.record_client_operation_duration"
)
async def test_AfterModel_ShouldHandleMissingUsageMetadata_WhenLlmResponseLacksTokens(
    mock_record_duration,
    mock_record_tokens,
):
    plugin = ObservabilityPlugin()
    mock_callback_ctx = MagicMock()
    mock_callback_ctx.invocation_id = "inv-model-2"
    mock_callback_ctx.agent_name = "research_agent"

    llm_resp = LlmResponse(
        content=types.Content(parts=[types.Part(text="Response")]),
        usage_metadata=None,
        model_version="gemini-2.5-flash",
    )

    await plugin.after_model_callback(
        callback_context=mock_callback_ctx,
        llm_response=llm_resp,
    )

    mock_record_tokens.assert_called_once()


@pytest.mark.asyncio
@patch("agent.core_agent.plugins.observability_plugin.plugin.agent_invocation_errors")
@patch(
    "agent.core_agent.plugins.observability_plugin.plugin.record_client_operation_duration"
)
async def test_OnModelError_ShouldRecordErrorDurationAndIncrementErrorCount_WhenLlmFails(
    mock_record_duration,
    mock_agent_errors,
):
    plugin = ObservabilityPlugin()
    mock_callback_ctx = MagicMock()
    mock_callback_ctx.invocation_id = "inv-err-1"
    mock_callback_ctx.agent_name = "research_agent"

    llm_req = LlmRequest(model="gemini-2.5-flash")
    plugin._model_start_times["inv-err-1"] = 50.0

    test_err = RuntimeError("Vertex API rate limit exceeded")

    with patch("time.perf_counter", return_value=51.5):
        await plugin.on_model_error_callback(
            callback_context=mock_callback_ctx,
            llm_request=llm_req,
            error=test_err,
        )

    mock_record_duration.assert_called_once_with(
        agent_name="research_agent",
        elapsed_s=pytest.approx(1.5),
        llm_request=llm_req,
        responses=[],
        error=test_err,
    )
    mock_agent_errors.add.assert_called_once_with(
        1,
        {
            "gen_ai.agent.name": "research_agent",
            "error.type": "RuntimeError",
        },
    )


# ─── ObservabilityPlugin Tool Lifecycle Tests ────────────────────────────────


@pytest.mark.asyncio
@patch("agent.core_agent.plugins.observability_plugin.plugin.tool_execution_requests")
@patch(
    "agent.core_agent.plugins.observability_plugin.plugin.record_tool_execution_duration"
)
async def test_ToolLifecycle_ShouldRecordToolDurationAndRequests_WhenToolRuns(
    mock_record_tool_duration,
    mock_tool_requests,
):
    plugin = ObservabilityPlugin()
    mock_tool = MagicMock()
    mock_tool.name = "search_google_drive"

    mock_tool_ctx = MagicMock()
    mock_tool_ctx.agent_name = "ingestion_agent"

    with patch("time.perf_counter", return_value=20.0):
        await plugin.before_tool_callback(
            tool=mock_tool,
            tool_args={"query": "test"},
            tool_context=mock_tool_ctx,
        )

    mock_tool_requests.add.assert_called_once_with(
        1,
        {
            "gen_ai.tool.name": "search_google_drive",
            "gen_ai.agent.name": "ingestion_agent",
        },
    )

    with patch("time.perf_counter", return_value=20.8):
        await plugin.after_tool_callback(
            tool=mock_tool,
            tool_args={"query": "test"},
            tool_context=mock_tool_ctx,
            result={"status": "ok"},
        )

    mock_record_tool_duration.assert_called_once_with(
        tool_name="search_google_drive",
        agent_name="ingestion_agent",
        elapsed_s=pytest.approx(0.8),
    )


@pytest.mark.asyncio
@patch("agent.core_agent.plugins.observability_plugin.plugin.tool_execution_errors")
@patch(
    "agent.core_agent.plugins.observability_plugin.plugin.record_tool_execution_duration"
)
async def test_OnToolError_ShouldRecordErrorMetrics_WhenToolExecutionFails(
    mock_record_tool_duration,
    mock_tool_errors,
):
    plugin = ObservabilityPlugin()
    mock_tool = MagicMock()
    mock_tool.name = "execute_bigquery_query"

    mock_tool_ctx = MagicMock()
    mock_tool_ctx.agent_name = "research_agent"

    plugin._tool_start_times[(id(mock_tool_ctx), mock_tool.name)] = 30.0

    tool_err = ValueError("Invalid SQL syntax")

    with patch("time.perf_counter", return_value=30.4):
        await plugin.on_tool_error_callback(
            tool=mock_tool,
            tool_args={"query": "SELECT *"},
            tool_context=mock_tool_ctx,
            error=tool_err,
        )

    mock_record_tool_duration.assert_called_once_with(
        tool_name="execute_bigquery_query",
        agent_name="research_agent",
        elapsed_s=pytest.approx(0.4),
        error=tool_err,
    )
    mock_tool_errors.add.assert_called_once_with(
        1,
        {
            "gen_ai.tool.name": "execute_bigquery_query",
            "gen_ai.agent.name": "research_agent",
            "error.type": "ValueError",
        },
    )
