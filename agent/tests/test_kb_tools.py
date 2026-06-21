import asyncio
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from agent.core_agent.tools.ekb_tools.tools import (
    TriggerEKBPipelineTool,
    CheckIngestionStatusTool,
)
from agent.core_agent.tools.ekb_tools.config import EKB_TOOLS_CONFIG

PENDING_INGESTIONS_KEY = EKB_TOOLS_CONFIG.SESSION_STATE_PENDING_JOBS_KEY


pytestmark = pytest.mark.asyncio


def _make_mock_response(
    status_code: int, json_body: dict, raise_error: Exception | None = None
):
    """Builds a reusable mock HTTP response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_body
    if raise_error:
        mock.raise_for_status.side_effect = raise_error
    else:
        mock.raise_for_status = MagicMock()
    return mock


def _build_async_client_mock(response: MagicMock, method: str = "post") -> MagicMock:
    """
    Builds an AsyncClient context-manager mock that returns the given response
    when the specified HTTP method is awaited.
    """
    client_mock = MagicMock()
    setattr(client_mock, method, AsyncMock(return_value=response))
    async_ctx_mock = MagicMock()
    async_ctx_mock.__aenter__ = AsyncMock(return_value=client_mock)
    async_ctx_mock.__aexit__ = AsyncMock(return_value=False)
    return async_ctx_mock


# ---------------------------------------------------------------------------
# TriggerEKBPipelineTool
# ---------------------------------------------------------------------------


class TestTriggerEKBPipelineTool:
    @patch("agent.core_agent.tools.ekb_tools.tools.get_id_token")
    @patch("agent.core_agent.tools.ekb_tools.tools.httpx.AsyncClient")
    async def test_returns_success_result_per_file_when_pipeline_responds(
        self, mock_async_client_cls, mock_get_token
    ):
        """Happy path: pipeline is triggered successfully with OIDC auth."""
        mock_get_token.return_value = "mock-id-token"

        mock_response = _make_mock_response(200, {"job_id": "job-abc-123"})
        mock_async_client_cls.return_value = _build_async_client_mock(
            mock_response, "post"
        )

        tool = TriggerEKBPipelineTool()
        ctx = MagicMock()
        ctx.state = {}

        args = {"gcs_uris": ["gs://mock-project-id-kb-landing-zone/project/doc.pdf"]}
        result = await tool.run_async(args=args, tool_context=ctx)

        assert isinstance(result, dict)
        responses = result["job_responses"]
        assert len(responses) == 1
        assert responses[0]["execution_status"] == "success"
        assert responses[0]["job_id"] == "job-abc-123"

    @patch("agent.core_agent.tools.ekb_tools.tools.get_id_token")
    @patch("agent.core_agent.tools.ekb_tools.tools.httpx.AsyncClient")
    async def test_stores_pending_job_in_session_state_when_ingestion_succeeds(
        self, mock_async_client_cls, mock_get_token
    ):
        """Happy path: job_id and filename are persisted in tool_context state."""
        mock_get_token.return_value = "mock-id-token"

        mock_response = _make_mock_response(200, {"job_id": "job-xyz-789"})
        mock_async_client_cls.return_value = _build_async_client_mock(
            mock_response, "post"
        )

        tool = TriggerEKBPipelineTool()
        ctx = MagicMock()
        ctx.state = {}

        await tool.run_async(
            args={
                "gcs_uris": ["gs://mock-project-id-kb-landing-zone/project/report.pdf"]
            },
            tool_context=ctx,
        )

        pending = ctx.state.get(PENDING_INGESTIONS_KEY, [])
        assert len(pending) == 1
        assert pending[0]["job_id"] == "job-xyz-789"
        assert pending[0]["filename"] == "report.pdf"

    @patch("agent.core_agent.tools.ekb_tools.tools.get_id_token")
    @patch("agent.core_agent.tools.ekb_tools.tools.httpx.AsyncClient")
    async def test_returns_result_per_file_and_stores_all_jobs_when_batch_provided(
        self, mock_async_client_cls, mock_get_token
    ):
        """
        Happy path: a single call with multiple URIs triggers all pipelines in
        parallel and stores all job entries in session state.
        """
        mock_get_token.return_value = "mock-id-token"

        responses = [
            _make_mock_response(200, {"job_id": "job-file-1"}),
            _make_mock_response(200, {"job_id": "job-file-2"}),
        ]
        client_mock = MagicMock()
        client_mock.post = AsyncMock(side_effect=responses)
        async_ctx = MagicMock()
        async_ctx.__aenter__ = AsyncMock(return_value=client_mock)
        async_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_async_client_cls.return_value = async_ctx

        tool = TriggerEKBPipelineTool()
        ctx = MagicMock()
        ctx.state = {}

        result = await tool.run_async(
            args={
                "gcs_uris": [
                    "gs://mock-project-id-kb-landing-zone/project/file1.pdf",
                    "gs://mock-project-id-kb-landing-zone/project/file2.pdf",
                ]
            },
            tool_context=ctx,
        )

        assert isinstance(result, dict)
        responses = result["job_responses"]
        assert len(responses) == 2
        assert responses[0]["execution_status"] == "success"
        assert responses[0]["job_id"] == "job-file-1"
        assert responses[1]["execution_status"] == "success"
        assert responses[1]["job_id"] == "job-file-2"

        pending = ctx.state.get(PENDING_INGESTIONS_KEY, [])
        assert len(pending) == 2
        assert pending[0]["filename"] == "file1.pdf"
        assert pending[1]["filename"] == "file2.pdf"

    @patch("agent.core_agent.tools.ekb_tools.tools.get_id_token")
    async def test_returns_error_per_uri_when_id_token_unavailable(
        self, mock_get_token
    ):
        """Failure mode: tool fails gracefully when ID token cannot be obtained."""
        mock_get_token.return_value = None

        tool = TriggerEKBPipelineTool()
        ctx = MagicMock()

        args = {"gcs_uris": ["gs://mock-project-id-kb-landing-zone/project/doc.pdf"]}
        result = await tool.run_async(args=args, tool_context=ctx)

        assert isinstance(result, dict)
        responses = result["job_responses"]
        assert len(responses) == 1
        assert responses[0]["execution_status"] == "error"
        assert "Authentication failed" in responses[0]["execution_message"]
        assert responses[0].get("job_id") in [None, "N/A"]

    async def test_returns_validation_error_when_gcs_uris_missing(self):
        """Edge case: missing 'gcs_uris' returns a validation error response."""
        tool = TriggerEKBPipelineTool()
        ctx = MagicMock()

        result = await tool.run_async(args={}, tool_context=ctx)

        assert isinstance(result, dict)
        responses = result["job_responses"]
        assert len(responses) == 1
        assert responses[0]["execution_status"] == "error"
        assert "validationerror" in responses[0]["execution_message"].lower()

    async def test_returns_error_when_uri_fails_gcs_pattern_validation(self):
        """Edge case: a URI that fails the gs:// pattern validator is caught and returned."""
        tool = TriggerEKBPipelineTool()
        ctx = MagicMock()

        result = await tool.run_async(
            args={"gcs_uris": ["https://not-a-gcs-uri/file.pdf"]},
            tool_context=ctx,
        )

        assert isinstance(result, dict)
        responses = result["job_responses"]
        assert len(responses) == 1
        assert responses[0]["execution_status"] == "error"
        assert "validationerror" in responses[0]["execution_message"].lower()

    @patch("agent.core_agent.tools.ekb_tools.tools.get_id_token")
    @patch("agent.core_agent.tools.ekb_tools.tools.httpx.AsyncClient")
    async def test_returns_mixed_results_and_stores_only_successes_when_some_files_fail(
        self, mock_async_client_cls, mock_get_token
    ):
        """
        Failure mode: one file fails while others succeed — the batch still returns
        a result per URI and only successful jobs are stored in state.
        """
        mock_get_token.return_value = "mock-id-token"

        http_error = httpx.HTTPStatusError(
            message="Internal Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500, text="Internal Server Error"),
        )
        responses = [
            _make_mock_response(200, {"job_id": "job-ok"}),
            _make_mock_response(500, {}, raise_error=http_error),
        ]
        client_mock = MagicMock()
        client_mock.post = AsyncMock(side_effect=responses)
        async_ctx = MagicMock()
        async_ctx.__aenter__ = AsyncMock(return_value=client_mock)
        async_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_async_client_cls.return_value = async_ctx

        tool = TriggerEKBPipelineTool()
        ctx = MagicMock()
        ctx.state = {}

        result = await tool.run_async(
            args={
                "gcs_uris": [
                    "gs://mock-project-id-kb-landing-zone/project/good.pdf",
                    "gs://mock-project-id-kb-landing-zone/project/bad.pdf",
                ]
            },
            tool_context=ctx,
        )

        assert isinstance(result, dict)
        responses = result["job_responses"]
        assert len(responses) == 2
        assert responses[0]["execution_status"] == "success"
        assert responses[1]["execution_status"] == "error"

        pending = ctx.state.get(PENDING_INGESTIONS_KEY, [])
        assert len(pending) == 1
        assert pending[0]["filename"] == "good.pdf"

    @patch("agent.core_agent.tools.ekb_tools.tools.get_id_token")
    @patch("agent.core_agent.tools.ekb_tools.tools.httpx.AsyncClient")
    async def test_returns_error_when_service_connection_times_out(
        self, mock_async_client_cls, mock_get_token
    ):
        """
        Failure mode: Cloud Run cold-start causes a ReadTimeout.
        The tool must return execution_status='error' rather than raising.
        """
        mock_get_token.return_value = "mock-id-token"

        client_mock = MagicMock()
        client_mock.post = AsyncMock(side_effect=httpx.ReadTimeout(""))
        async_ctx = MagicMock()
        async_ctx.__aenter__ = AsyncMock(return_value=client_mock)
        async_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_async_client_cls.return_value = async_ctx

        tool = TriggerEKBPipelineTool()
        ctx = MagicMock()

        result = await tool.run_async(
            args={"gcs_uris": ["gs://mock-project-id-kb-landing-zone/project/doc.pdf"]},
            tool_context=ctx,
        )

        assert isinstance(result, dict)
        responses = result["job_responses"]
        assert responses[0]["execution_status"] == "error"
        assert "ReadTimeout" in responses[0]["execution_message"]

    @patch("agent.core_agent.tools.ekb_tools.tools.get_id_token")
    @patch("agent.core_agent.tools.ekb_tools.tools.httpx.AsyncClient")
    async def test_uses_minimum_120s_timeout_per_request_to_survive_cold_starts(
        self, mock_async_client_cls, mock_get_token
    ):
        """
        Regression guard: the POST to the EKB pipeline must use a timeout of at
        least 120 seconds to survive Cloud Run cold starts.
        """
        mock_get_token.return_value = "mock-id-token"

        post_mock = AsyncMock(
            return_value=_make_mock_response(200, {"job_id": "job-timeout-check"})
        )
        client_mock = MagicMock()
        client_mock.post = post_mock
        async_ctx = MagicMock()
        async_ctx.__aenter__ = AsyncMock(return_value=client_mock)
        async_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_async_client_cls.return_value = async_ctx

        tool = TriggerEKBPipelineTool()
        ctx = MagicMock()
        ctx.state = {}

        await tool.run_async(
            args={"gcs_uris": ["gs://mock-project-id-kb-landing-zone/project/doc.pdf"]},
            tool_context=ctx,
        )

        _, call_kwargs = post_mock.call_args
        actual_timeout = call_kwargs.get("timeout", 0)
        assert actual_timeout >= 120.0, (
            f"EKB pipeline POST timeout is {actual_timeout}s — must be ≥ 120s "
            "to survive Cloud Run cold starts"
        )


# ---------------------------------------------------------------------------
# CheckIngestionStatusTool
# ---------------------------------------------------------------------------


class TestCheckIngestionStatusTool:
    @patch("agent.core_agent.tools.ekb_tools.tools.get_id_token")
    @patch("agent.core_agent.tools.ekb_tools.tools.httpx.AsyncClient")
    async def test_check_status_success(self, mock_async_client_cls, mock_get_token):
        """Happy path: returns full status response for a known job."""
        mock_get_token.return_value = "mock-id-token"

        status_payload = {
            "job_id": "job-abc-123",
            "status": "success",
            "message": "Pipeline completed.",
            "gcs_uri": "gs://kb-domain/it/doc.pdf",
            "chunks_generated": 42,
            "final_domain": "it",
            "security_tier": "tier-1",
        }
        mock_response = _make_mock_response(200, status_payload)
        mock_async_client_cls.return_value = _build_async_client_mock(
            mock_response, "get"
        )

        tool = CheckIngestionStatusTool()
        ctx = MagicMock()

        result = await tool.run_async(args={"job_id": "job-abc-123"}, tool_context=ctx)

        assert result["execution_status"] == "success"
        assert result["job_id"] == "job-abc-123"
        assert result["job_status"] == "success"
        assert result["chunks_generated"] == 42

    @patch("agent.core_agent.tools.ekb_tools.tools.get_id_token")
    async def test_check_status_auth_failure(self, mock_get_token):
        """Failure mode: graceful degradation when auth token is unavailable."""
        mock_get_token.return_value = None

        tool = CheckIngestionStatusTool()
        ctx = MagicMock()

        result = await tool.run_async(args={"job_id": "job-abc-123"}, tool_context=ctx)

        assert result["execution_status"] == "error"
        assert (
            "Auth failed" in result["execution_message"]
            or "Authentication" in result["execution_message"]
        )

    async def test_check_status_missing_job_id(self):
        """Edge case: missing 'job_id' argument raises a validation error."""
        tool = CheckIngestionStatusTool()
        ctx = MagicMock()

        result = await tool.run_async(args={}, tool_context=ctx)

        assert result["execution_status"] == "error"

    @patch("agent.core_agent.tools.ekb_tools.tools.get_id_token")
    @patch("agent.core_agent.tools.ekb_tools.tools.httpx.AsyncClient")
    async def test_check_status_service_unavailable(
        self, mock_async_client_cls, mock_get_token
    ):
        """Failure mode: network error during status check is caught and returned."""
        mock_get_token.return_value = "mock-id-token"

        client_mock = MagicMock()
        client_mock.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        async_ctx = MagicMock()
        async_ctx.__aenter__ = AsyncMock(return_value=client_mock)
        async_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_async_client_cls.return_value = async_ctx

        tool = CheckIngestionStatusTool()
        ctx = MagicMock()

        result = await tool.run_async(args={"job_id": "job-abc-123"}, tool_context=ctx)

        assert result["execution_status"] == "error"

    @patch("agent.core_agent.tools.ekb_tools.tools.get_id_token")
    @patch("agent.core_agent.tools.ekb_tools.tools.httpx.AsyncClient")
    async def test_check_status_concurrent_calls(
        self, mock_async_client_cls, mock_get_token
    ):
        """
        Regression test: concurrent status checks for two different jobs must
        each return the correct, independent results without cross-contamination.
        """
        mock_get_token.return_value = "mock-id-token"

        job1_payload = {"job_id": "job-1", "status": "success", "message": "Done."}
        job2_payload = {
            "job_id": "job-2",
            "status": "processing",
            "message": "Still running.",
        }

        mock_async_client_cls.side_effect = [
            _build_async_client_mock(_make_mock_response(200, job1_payload), "get"),
            _build_async_client_mock(_make_mock_response(200, job2_payload), "get"),
        ]

        tool = CheckIngestionStatusTool()
        ctx = MagicMock()

        result1, result2 = await asyncio.gather(
            tool.run_async(args={"job_id": "job-1"}, tool_context=ctx),
            tool.run_async(args={"job_id": "job-2"}, tool_context=ctx),
        )

        assert result1["job_id"] == "job-1"
        assert result1["job_status"] == "success"
        assert result2["job_id"] == "job-2"
        assert result2["job_status"] == "processing"
