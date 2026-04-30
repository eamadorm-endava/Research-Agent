import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.core_agent.plugins.storage.callbacks import PENDING_RENDER_KEY
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
    async def test_multimodal_file_is_saved_as_file_data_reference(self):
        """Happy path: multimodal file is registered using its GCS URI reference."""
        tool = ImportGcsToArtifactTool()
        ctx = _make_mock_tool_context(save_artifact_version=1)

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/photo.png", "mime_type": "image/png"},
            tool_context=ctx,
        )

        assert result["execution_status"] == "success"
        assert result["content_type"] == "image/png"
        saved_part = ctx.save_artifact.call_args.kwargs["artifact"]
        assert saved_part.file_data is not None
        assert saved_part.file_data.file_uri == "gs://bucket/photo.png"
        assert saved_part.file_data.mime_type == "image/png"

    async def test_text_file_is_also_saved_as_file_data_reference(self):
        """Happy path: text file is also registered as a URI reference to avoid downloads."""
        tool = ImportGcsToArtifactTool()
        ctx = _make_mock_tool_context()

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/notes.txt", "mime_type": "text/plain"},
            tool_context=ctx,
        )

        assert result["execution_status"] == "success"
        saved_part = ctx.save_artifact.call_args.kwargs["artifact"]
        assert saved_part.file_data.file_uri == "gs://bucket/notes.txt"
        assert saved_part.file_data.mime_type == "text/plain"

    async def test_mime_type_guessing_from_extension(self):
        """Edge case: MIME type is correctly guessed from URI extension when missing."""
        tool = ImportGcsToArtifactTool()
        ctx = _make_mock_tool_context()

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/report.pdf"}, tool_context=ctx
        )

        assert result["execution_status"] == "success"
        assert result["content_type"] == "application/pdf"
        saved_part = ctx.save_artifact.call_args.kwargs["artifact"]
        assert saved_part.file_data.mime_type == "application/pdf"

    async def test_explicit_artifact_name_overrides_derived_name(self):
        """Edge case: caller-provided artifact_name takes priority over the GCS filename."""
        tool = ImportGcsToArtifactTool()
        ctx = _make_mock_tool_context()

        await tool.run_async(
            args={
                "gcs_uri": "gs://bucket/original.txt",
                "artifact_name": "my_custom.txt",
            },
            tool_context=ctx,
        )

        ctx.save_artifact.assert_called_once()
        assert ctx.save_artifact.call_args.kwargs["filename"] == "my_custom.txt"

    async def test_artifact_id_encodes_name_and_version(self):
        """Edge case: returned artifact_id correctly encodes the name and version number."""
        tool = ImportGcsToArtifactTool()
        ctx = _make_mock_tool_context(save_artifact_version=3)

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/notes.txt"}, tool_context=ctx
        )

        assert result["artifact_id"] == "notes.txt:v3"

    async def test_queues_artifact_filename_in_state_for_ge_rendering(self):
        """Edge case: after a successful save, the filename is added to the GE render queue in state."""
        tool = ImportGcsToArtifactTool()
        ctx = _make_mock_tool_context()

        await tool.run_async(
            args={"gcs_uri": "gs://bucket/report.txt"}, tool_context=ctx
        )

        ctx.state.__setitem__.assert_called_with(PENDING_RENDER_KEY, ["report.txt"])

    async def test_returns_error_on_malformed_args(self):
        """Failure mode: missing required 'gcs_uri' returns error dict instead of raising."""
        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()

        result = await tool.run_async(args={}, tool_context=ctx)

        assert result["execution_status"] == "error"
        assert result["gcs_uri"] is None
