import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.core_agent.plugins.storage.callbacks import (
    PENDING_URI_KEY,
)
from agent.core_agent.plugins.storage.tools import (
    GetArtifactUriTool,
    ImportGcsToArtifactTool,
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


# ─── GetArtifactUriTool ───────────────────────────────────────────────────────


class TestGetArtifactUriTool:
    async def test_returns_gcs_uri_when_artifact_found(self):
        """Happy path: artifact exists in session, returns its canonical GCS URI."""
        tool = GetArtifactUriTool()
        ctx = AsyncMock()
        mock_version = MagicMock()
        mock_version.canonical_uri = "gs://test-bucket/sessions/abc/report.pdf"
        ctx.get_artifact_version.return_value = mock_version

        result = await tool.run_async(args={"filename": "report.pdf"}, tool_context=ctx)

        assert result["execution_status"] == "success"
        assert result["gcs_uri"] == "gs://test-bucket/sessions/abc/report.pdf"

    async def test_returns_error_when_artifact_not_found(self):
        """Failure mode: artifact does not exist in the current session."""
        tool = GetArtifactUriTool()
        ctx = AsyncMock()
        ctx.get_artifact_version.return_value = None

        result = await tool.run_async(args={"filename": "ghost.pdf"}, tool_context=ctx)

        assert result["execution_status"] == "error"
        assert result["gcs_uri"] is None
        assert "ghost.pdf" in result["execution_message"]

    async def test_returns_error_on_service_exception(self):
        """Failure mode: artifact service raises an unexpected exception."""
        tool = GetArtifactUriTool()
        ctx = AsyncMock()
        ctx.get_artifact_version.side_effect = RuntimeError("Storage unavailable")

        result = await tool.run_async(args={"filename": "report.pdf"}, tool_context=ctx)

        assert result["execution_status"] == "error"
        assert result["gcs_uri"] is None
        assert "Storage unavailable" in result["execution_message"]

    async def test_forwards_optional_version_to_artifact_service(self):
        """Edge case: optional version parameter is forwarded to the artifact service."""
        tool = GetArtifactUriTool()
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
        tool = GetArtifactUriTool()
        ctx = AsyncMock()

        result = await tool.run_async(args={}, tool_context=ctx)

        assert result["execution_status"] == "error"
        assert result["gcs_uri"] is None


# ─── ImportGcsToArtifactTool ──────────────────────────────────────────────────


class TestImportGcsToArtifactTool:
    async def test_import_gcs_uri_is_queued_for_direct_pass_through(self):
        """Happy path: GCS URI is registered in state for zero-copy rendering."""
        tool = ImportGcsToArtifactTool()
        ctx = _make_mock_tool_context()

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/photo.png", "mime_type": "image/png"},
            tool_context=ctx,
        )

        assert result["execution_status"] == "success"
        assert result["content_type"] == "image/png"
        assert result["artifact_id"] == "photo.png:direct"

        # Verify zero-copy: save_artifact MUST NOT be called
        ctx.save_artifact.assert_not_called()

        # Verify state queuing
        ctx.state.__setitem__.assert_called_with(
            PENDING_URI_KEY,
            [{"uri": "gs://bucket/photo.png", "mime_type": "image/png"}],
        )

    async def test_mime_type_guessing_from_extension(self):
        """Edge case: MIME type is correctly guessed from URI extension when missing."""
        tool = ImportGcsToArtifactTool()
        ctx = _make_mock_tool_context()

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/report.pdf"}, tool_context=ctx
        )

        assert result["execution_status"] == "success"
        assert result["content_type"] == "application/pdf"

        # Verify state queuing with guessed MIME
        ctx.state.__setitem__.assert_called_with(
            PENDING_URI_KEY,
            [{"uri": "gs://bucket/report.pdf", "mime_type": "application/pdf"}],
        )

    async def test_explicit_artifact_name_overrides_derived_id(self):
        """Edge case: caller-provided artifact_name is reflected in the returned artifact_id."""
        tool = ImportGcsToArtifactTool()
        ctx = _make_mock_tool_context()

        result = await tool.run_async(
            args={
                "gcs_uri": "gs://bucket/original.txt",
                "artifact_name": "my_custom.txt",
            },
            tool_context=ctx,
        )

        assert result["artifact_id"] == "my_custom.txt:direct"

    async def test_returns_error_on_malformed_args(self):
        """Failure mode: missing required 'gcs_uri' returns error dict instead of raising."""
        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()

        result = await tool.run_async(args={}, tool_context=ctx)

        assert result["execution_status"] == "error"
        assert result["gcs_uri"] is None
