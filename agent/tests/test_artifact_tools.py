import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.core_agent.tools.artifact_tools import (
    GetArtifactURITool,
)

pytestmark = pytest.mark.asyncio


# ─── Shared helpers ───────────────────────────────────────────────────────────


def _make_mock_tool_context(save_artifact_version: int = 0) -> AsyncMock:
    """Builds a ToolContext mock with a real dict-backed state and a configured save_artifact."""
    ctx = AsyncMock()
    ctx.save_artifact.return_value = save_artifact_version
    _state: dict = {}
    ctx.state = MagicMock()
    ctx.state.get = MagicMock(side_effect=lambda k, d=None: _state.get(k, d))
    ctx.state.__setitem__ = MagicMock(side_effect=lambda k, v: _state.update({k: v}))
    ctx.state.__getitem__ = MagicMock(side_effect=lambda k: _state[k])
    ctx.state.__contains__ = MagicMock(side_effect=lambda k: k in _state)
    return ctx


# ─── GetArtifactURITool ───────────────────────────────────────────────────────


class TestGetArtifactURITool:
    async def test_returns_gcs_uri_when_artifact_found(self):
        """Happy path: artifact exists in session, returns its canonical GCS URI."""
        tool = GetArtifactURITool()
        ctx = AsyncMock()
        mock_version = MagicMock()
        mock_version.canonical_uri = "gs://test-bucket/sessions/abc/report.pdf"
        ctx.get_artifact_version.return_value = mock_version

        result = await tool.run_async(args={"filename": "report.pdf"}, tool_context=ctx)

        assert result["execution_status"] == "success"
        assert result["gcs_uri"] == "gs://test-bucket/sessions/abc/report.pdf"

    async def test_returns_error_when_artifact_not_found(self):
        """Failure mode: artifact does not exist in the current session."""
        tool = GetArtifactURITool()
        ctx = AsyncMock()
        ctx.get_artifact_version.return_value = None

        result = await tool.run_async(args={"filename": "ghost.pdf"}, tool_context=ctx)

        assert result["execution_status"] == "error"
        assert result["gcs_uri"] is None
        assert "ghost.pdf" in result["execution_message"]

    async def test_returns_error_on_service_exception(self):
        """Failure mode: artifact service raises an unexpected exception."""
        tool = GetArtifactURITool()
        ctx = AsyncMock()
        ctx.get_artifact_version.side_effect = RuntimeError("Storage unavailable")

        result = await tool.run_async(args={"filename": "report.pdf"}, tool_context=ctx)

        assert result["execution_status"] == "error"
        assert result["gcs_uri"] is None
        assert "Storage unavailable" in result["execution_message"]

    async def test_forwards_optional_version_to_artifact_service(self):
        """Edge case: optional version parameter is forwarded to the artifact service."""
        tool = GetArtifactURITool()
        ctx = AsyncMock()
        mock_version = MagicMock()
        mock_version.canonical_uri = "gs://bucket/file.pdf"
        ctx.get_artifact_version.return_value = mock_version

        await tool.run_async(
            args={"filename": "file.pdf", "version": 2}, tool_context=ctx
        )

        ctx.get_artifact_version.assert_called_once_with(filename="file.pdf", version=2)

    async def test_returns_error_on_malformed_args(self):
        """Failure mode: missing required 'filename' returns error dict instead of raising."""
        tool = GetArtifactURITool()
        ctx = AsyncMock()

        result = await tool.run_async(args={}, tool_context=ctx)

        assert result["execution_status"] == "error"
        assert result["gcs_uri"] is None
