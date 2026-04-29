import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.core_agent.internal_tools.artifacts.tools import (
    GetArtifactUriTool,
    ImportGcsToArtifactTool,
)

pytestmark = pytest.mark.asyncio


# ─── Shared helpers ───────────────────────────────────────────────────────────


def _make_mock_blob(
    data: bytes,
    content_type: str | None,
    exists: bool = True,
) -> MagicMock:
    blob = MagicMock()
    blob.exists.return_value = exists
    blob.download_as_bytes.return_value = data
    blob.content_type = content_type
    return blob


def _make_mock_storage_client(blob: MagicMock) -> MagicMock:
    client = MagicMock()
    client.bucket.return_value.blob.return_value = blob
    return client


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
    @patch("agent.core_agent.internal_tools.artifacts.tools.storage")
    async def test_image_file_is_saved_as_inline_data(self, mock_storage):
        """Happy path: image file is imported and stored as an inline-data artifact."""
        blob = _make_mock_blob(b"fake-png-bytes", "image/png")
        mock_storage.Client.return_value = _make_mock_storage_client(blob)

        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()
        ctx.save_artifact.return_value = 1

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/photo.png"}, tool_context=ctx
        )

        assert result["execution_status"] == "success"
        assert result["content_type"] == "image/png"
        saved_part = ctx.save_artifact.call_args.kwargs["artifact"]
        assert saved_part.inline_data is not None
        assert saved_part.inline_data.mime_type == "image/png"

    @patch("agent.core_agent.internal_tools.artifacts.tools.storage")
    async def test_pdf_file_is_saved_as_inline_data(self, mock_storage):
        """Happy path: PDF is imported as inline-data so Gemini can read it natively."""
        blob = _make_mock_blob(b"%PDF-fake", "application/pdf")
        mock_storage.Client.return_value = _make_mock_storage_client(blob)

        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()
        ctx.save_artifact.return_value = 0

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/report.pdf"}, tool_context=ctx
        )

        assert result["execution_status"] == "success"
        saved_part = ctx.save_artifact.call_args.kwargs["artifact"]
        assert saved_part.inline_data.mime_type == "application/pdf"

    @patch("agent.core_agent.internal_tools.artifacts.tools.storage")
    async def test_audio_file_is_saved_as_inline_data(self, mock_storage):
        """Happy path: audio file is imported as inline-data for multimodal analysis."""
        blob = _make_mock_blob(b"fake-mp3-bytes", "audio/mpeg")
        mock_storage.Client.return_value = _make_mock_storage_client(blob)

        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()
        ctx.save_artifact.return_value = 0

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/meeting.mp3"}, tool_context=ctx
        )

        assert result["execution_status"] == "success"
        saved_part = ctx.save_artifact.call_args.kwargs["artifact"]
        assert saved_part.inline_data.mime_type == "audio/mpeg"

    @patch("agent.core_agent.internal_tools.artifacts.tools.storage")
    async def test_plain_text_file_is_saved_as_text_part(self, mock_storage):
        """Happy path: plain-text file is imported as a text Part."""
        blob = _make_mock_blob(b"Hello, World!", "text/plain")
        mock_storage.Client.return_value = _make_mock_storage_client(blob)

        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()
        ctx.save_artifact.return_value = 0

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/notes.txt"}, tool_context=ctx
        )

        assert result["execution_status"] == "success"
        saved_part = ctx.save_artifact.call_args.kwargs["artifact"]
        assert saved_part.text == "Hello, World!"

    @patch("agent.core_agent.internal_tools.artifacts.tools.storage")
    async def test_csv_file_is_saved_as_text_part(self, mock_storage):
        """Happy path: CSV file is treated as text-like and imported accordingly."""
        csv_bytes = b"col1,col2\n1,2\n3,4"
        blob = _make_mock_blob(csv_bytes, "application/csv")
        mock_storage.Client.return_value = _make_mock_storage_client(blob)

        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()
        ctx.save_artifact.return_value = 0

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/data.csv"}, tool_context=ctx
        )

        assert result["execution_status"] == "success"
        saved_part = ctx.save_artifact.call_args.kwargs["artifact"]
        assert "col1" in saved_part.text

    @patch("agent.core_agent.internal_tools.artifacts.tools.storage")
    async def test_unsupported_binary_falls_back_to_placeholder_text(
        self, mock_storage
    ):
        """Edge case: unknown binary MIME type falls back to a descriptive placeholder."""
        blob = _make_mock_blob(b"\x00\x01\x02", "application/octet-stream")
        mock_storage.Client.return_value = _make_mock_storage_client(blob)

        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()
        ctx.save_artifact.return_value = 0

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/data.bin"}, tool_context=ctx
        )

        assert result["execution_status"] == "success"
        saved_part = ctx.save_artifact.call_args.kwargs["artifact"]
        assert "[Binary Artifact:" in saved_part.text
        assert "application/octet-stream" in saved_part.text

    @patch("agent.core_agent.internal_tools.artifacts.tools.storage")
    async def test_explicit_artifact_name_overrides_derived_name(self, mock_storage):
        """Edge case: caller-provided artifact_name takes priority over the GCS filename."""
        blob = _make_mock_blob(b"data", "text/plain")
        mock_storage.Client.return_value = _make_mock_storage_client(blob)

        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()
        ctx.save_artifact.return_value = 0

        await tool.run_async(
            args={
                "gcs_uri": "gs://bucket/original.txt",
                "artifact_name": "my_custom.txt",
            },
            tool_context=ctx,
        )

        ctx.save_artifact.assert_called_once()
        assert ctx.save_artifact.call_args.kwargs["filename"] == "my_custom.txt"

    @patch("agent.core_agent.internal_tools.artifacts.tools.storage")
    async def test_artifact_id_encodes_name_and_version(self, mock_storage):
        """Edge case: returned artifact_id correctly encodes the name and version number."""
        blob = _make_mock_blob(b"data", "text/plain")
        mock_storage.Client.return_value = _make_mock_storage_client(blob)

        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()
        ctx.save_artifact.return_value = 3

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/notes.txt"}, tool_context=ctx
        )

        assert result["artifact_id"] == "notes.txt:v3"

    @patch("agent.core_agent.internal_tools.artifacts.tools.storage")
    async def test_explicit_mime_type_overrides_blob_content_type(self, mock_storage):
        """Edge case: caller-specified mime_type is used even when the blob has its own content_type."""
        blob = _make_mock_blob(b"data", "application/octet-stream")
        mock_storage.Client.return_value = _make_mock_storage_client(blob)

        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()
        ctx.save_artifact.return_value = 0

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/file", "mime_type": "text/plain"},
            tool_context=ctx,
        )

        assert result["content_type"] == "text/plain"

    @patch("agent.core_agent.internal_tools.artifacts.tools.mimetypes")
    @patch("agent.core_agent.internal_tools.artifacts.tools.storage")
    async def test_guesses_mime_type_from_extension_when_blob_has_none(
        self, mock_storage, mock_mimetypes
    ):
        """Edge case: when blob has no content_type, MIME type is guessed from the filename extension."""
        blob = _make_mock_blob(b"%PDF-fake", content_type=None)
        mock_storage.Client.return_value = _make_mock_storage_client(blob)
        mock_mimetypes.guess_type.return_value = ("application/pdf", None)

        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()
        ctx.save_artifact.return_value = 0

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/document.pdf"}, tool_context=ctx
        )

        assert result["execution_status"] == "success"
        assert result["content_type"] == "application/pdf"
        mock_mimetypes.guess_type.assert_called_once_with("document.pdf")

    @patch("agent.core_agent.internal_tools.artifacts.tools.storage")
    async def test_returns_error_when_gcs_object_not_found(self, mock_storage):
        """Failure mode: the GCS blob does not exist; save_artifact must not be called."""
        blob = _make_mock_blob(b"", content_type="text/plain", exists=False)
        mock_storage.Client.return_value = _make_mock_storage_client(blob)

        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/ghost.txt"}, tool_context=ctx
        )

        assert result["execution_status"] == "error"
        assert result["gcs_uri"] is None
        ctx.save_artifact.assert_not_called()

    @patch("agent.core_agent.internal_tools.artifacts.tools.storage")
    async def test_returns_error_on_storage_client_exception(self, mock_storage):
        """Failure mode: GCS client raises an unexpected exception during initialisation."""
        mock_storage.Client.side_effect = Exception("Network timeout")

        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/file.pdf"}, tool_context=ctx
        )

        assert result["execution_status"] == "error"
        assert result["gcs_uri"] is None
        assert "Network timeout" in result["execution_message"]

    async def test_returns_error_on_malformed_args(self):
        """Failure mode: missing required 'gcs_uri' returns error dict instead of raising."""
        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()

        result = await tool.run_async(args={}, tool_context=ctx)

        assert result["execution_status"] == "error"
        assert result["gcs_uri"] is None

    @patch("agent.core_agent.internal_tools.artifacts.tools.storage")
    async def test_non_utf8_text_is_decoded_with_replacement(self, mock_storage):
        """Edge case: text files with invalid UTF-8 sequences are decoded without crashing."""
        invalid_utf8 = b"Hello \xff\xfe World"
        blob = _make_mock_blob(invalid_utf8, "text/plain")
        mock_storage.Client.return_value = _make_mock_storage_client(blob)

        tool = ImportGcsToArtifactTool()
        ctx = AsyncMock()
        ctx.save_artifact.return_value = 0

        result = await tool.run_async(
            args={"gcs_uri": "gs://bucket/file.txt"}, tool_context=ctx
        )

        assert result["execution_status"] == "success"
        saved_part = ctx.save_artifact.call_args.kwargs["artifact"]
        assert "Hello" in saved_part.text
