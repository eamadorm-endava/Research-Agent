import pytest
from unittest.mock import AsyncMock, MagicMock

from google.genai import types
from agent.core_agent.plugins.gemini_enterprise_ingestion.main import (
    GeminiEnterpriseFileIngestionPlugin,
)

pytestmark = pytest.mark.asyncio

# ─── Shared helpers ───────────────────────────────────────────────────────────


def _make_text_part(text: str = "Hello") -> types.Part:
    return types.Part(text=text)


class FakeStorageService:
    def __init__(self, metadata=None):
        self.get_artifact_metadata = AsyncMock(return_value=metadata)
        self.ensure_uploader_permissions = AsyncMock()


def _make_invocation_context(
    artifact_service: FakeStorageService | None = None,
    metadata: dict | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.invocation_id = "inv-123"
    ctx.app_name = "test-app"
    ctx.user_id = "user-1"
    ctx.session = MagicMock()
    ctx.session.id = "session-1"

    if artifact_service is None:
        ctx.artifact_service = FakeStorageService(metadata=metadata)
    else:
        if not hasattr(artifact_service, "get_artifact_metadata"):
            artifact_service.get_artifact_metadata = AsyncMock(return_value=metadata)
        ctx.artifact_service = artifact_service

    return ctx


def _make_user_message(parts: list) -> types.Content:
    return types.Content(role="user", parts=parts)


def _make_ge_text_part(filename: str, content: str) -> list:
    """Build the 2-part GE text-extraction structure for a single file."""
    start = types.Part(text=f"\n<start_of_user_uploaded_file: {filename}>\n{content}\n")
    end = types.Part(text=f"<end_of_user_uploaded_file: {filename}>\n")
    return [start, end]


# ─── Happy Path ───────────────────────────────────────────────────────────────


async def test_ge_text_extracted_file_is_resolved_and_placeholder_returned():
    """Should resolve a GE text-extracted file via metadata and replace the tag block with file_data."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    text_part = types.Part(text="Summarize this")
    file_parts = _make_ge_text_part("report.pdf", "This is the extracted PDF text.")
    ctx = _make_invocation_context(
        metadata={"file_uri": "gs://bucket/report.pdf", "mime_type": "application/pdf"}
    )
    msg = _make_user_message([text_part] + file_parts)

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is not None
    ctx.artifact_service.get_artifact_metadata.assert_called_once()
    call_kwargs = ctx.artifact_service.get_artifact_metadata.call_args.kwargs
    assert call_kwargs["filename"] == "report.pdf"
    assert call_kwargs["user_id"] == "user-1"

    placeholder_texts = [p.text for p in result.parts if hasattr(p, "text") and p.text]
    assert any('[Uploaded Artifact: "report.pdf"]' in t for t in placeholder_texts)

    file_data_parts = [
        p.file_data for p in result.parts if getattr(p, "file_data", None)
    ]
    assert len(file_data_parts) == 1
    assert file_data_parts[0].file_uri == "gs://bucket/report.pdf"
    assert file_data_parts[0].mime_type == "application/pdf"

    # Should grant IAM permission
    ctx.artifact_service.ensure_uploader_permissions.assert_called_once_with(
        "gs://bucket/report.pdf", "user-1", "test-app"
    )


async def test_ge_text_extracted_file_preserves_non_file_text():
    """Should keep the user's prompt text and strip only the GE file tag block."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    text_part = _make_text_part("Summarize this")
    file_parts = _make_ge_text_part("doc.pdf", "PDF content here.")
    ctx = _make_invocation_context(
        metadata={"file_uri": "gs://bucket/doc.pdf", "mime_type": "application/pdf"}
    )
    msg = _make_user_message([text_part] + file_parts)

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is not None
    all_text = " ".join(p.text for p in result.parts if getattr(p, "text", None))
    assert "Summarize this" in all_text


async def test_multiple_ge_text_extracted_files_all_resolved():
    """Should resolve every GE text-extracted file found across all parts."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    parts_a = _make_ge_text_part("a.pdf", "Content of A.")
    parts_b = _make_ge_text_part("b.pdf", "Content of B.")

    svc = FakeStorageService()
    svc.get_artifact_metadata.side_effect = [
        {"file_uri": "gs://bucket/a.pdf", "mime_type": "application/pdf"},
        {"file_uri": "gs://bucket/b.pdf", "mime_type": "application/pdf"},
    ]

    ctx = _make_invocation_context(artifact_service=svc)
    msg = _make_user_message(parts_a + parts_b)

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is not None
    assert svc.get_artifact_metadata.call_count == 2

    file_data_parts = [
        p.file_data for p in result.parts if getattr(p, "file_data", None)
    ]
    assert len(file_data_parts) == 2


# ─── Failure Modes ────────────────────────────────────────────────────────────


async def test_ge_text_extracted_file_falls_back_on_metadata_failure():
    """Should restore the original tag block when artifact metadata lookup fails."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    file_parts = _make_ge_text_part("fail.pdf", "Some content.")

    svc = FakeStorageService()
    svc.get_artifact_metadata.side_effect = RuntimeError("GCS read error")

    ctx = _make_invocation_context(artifact_service=svc)
    msg = _make_user_message(file_parts)

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is not None
    assert any(
        "start_of_user_uploaded_file" in (getattr(p, "text", "") or "")
        for p in result.parts
    )


async def test_returns_empty_artifact_placeholder_when_metadata_returns_none():
    """Should return an empty artifact placeholder if metadata is None."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    file_parts = _make_ge_text_part("missing.pdf", "Some content.")

    ctx = _make_invocation_context(metadata=None)
    msg = _make_user_message(file_parts)

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is not None
    placeholder_texts = [p.text for p in result.parts if hasattr(p, "text") and p.text]
    assert any(
        '[Empty/Non-text Artifact: "missing.pdf"]' in t for t in placeholder_texts
    )


# ─── Edge Cases ───────────────────────────────────────────────────────────────


async def test_returns_none_when_no_artifact_service_available():
    """Should return None (pass through) when no artifact service is configured."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    ctx = _make_invocation_context()
    ctx.artifact_service = None
    msg = _make_user_message(_make_ge_text_part("doc.pdf", "text"))

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is None


async def test_returns_none_when_message_has_no_parts():
    """Should return None when the user message contains no parts."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    ctx = _make_invocation_context()
    msg = _make_user_message(parts=[])

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is None


async def test_returns_none_when_message_has_no_ge_text_blocks():
    """Should return None when no GE text blocks are present."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    ctx = _make_invocation_context()
    msg = _make_user_message([_make_text_part("Just a question, no file")])

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is None
