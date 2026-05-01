import pytest
import httpx
from unittest.mock import patch, MagicMock
from agent.core_agent.tools.kb_tools import TriggerEKBPipelineTool

pytestmark = pytest.mark.asyncio


class TestTriggerEKBPipelineTool:
    @patch("agent.core_agent.tools.kb_tools.get_id_token")
    @patch("httpx.AsyncClient.post")
    async def test_trigger_pipeline_success(self, mock_post, mock_get_token):
        """Happy path: pipeline is triggered successfully with OIDC auth."""
        mock_get_token.return_value = "mock-id-token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"job_id": "123"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        tool = TriggerEKBPipelineTool()
        ctx = MagicMock()

        args = {"gcs_uri": "gs://kb-landing-zone/project/doc.pdf"}
        result = await tool.run_async(args=args, tool_context=ctx)

        assert result["execution_status"] == "success"
        assert result["response"]["job_id"] == "123"
        mock_post.assert_called_once()
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer mock-id-token"

    @patch("agent.core_agent.tools.kb_tools.get_id_token")
    async def test_trigger_pipeline_auth_failure(self, mock_get_token):
        """Failure mode: tool fails gracefully when ID token cannot be obtained."""
        mock_get_token.return_value = None

        tool = TriggerEKBPipelineTool()
        ctx = MagicMock()

        args = {"gcs_uri": "gs://kb-landing-zone/project/doc.pdf"}
        result = await tool.run_async(args=args, tool_context=ctx)

        assert result["execution_status"] == "error"
        assert "Authentication failed" in result["execution_message"]

    async def test_trigger_pipeline_missing_args(self):
        """Failure mode: missing mandatory 'gcs_uri' returns Pydantic validation error."""
        tool = TriggerEKBPipelineTool()
        ctx = MagicMock()

        result = await tool.run_async(args={}, tool_context=ctx)

        assert result["execution_status"] == "error"
        assert "validation error" in result["execution_message"].lower()

    @patch("agent.core_agent.tools.kb_tools.get_id_token")
    @patch("httpx.AsyncClient.post")
    async def test_trigger_pipeline_service_error(self, mock_post, mock_get_token):
        """Failure mode: handles HTTP errors from the Cloud Run service."""
        mock_get_token.return_value = "mock-id-token"

        mock_post.side_effect = httpx.HTTPStatusError(
            message="Internal Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500, text="Internal Server Error"),
        )

        tool = TriggerEKBPipelineTool()
        ctx = MagicMock()

        args = {"gcs_uri": "gs://kb-landing-zone/project/doc.pdf"}
        result = await tool.run_async(args=args, tool_context=ctx)

        assert result["execution_status"] == "error"
        assert "Internal Error" in result["execution_message"]
