import pytest
from unittest.mock import AsyncMock, MagicMock
from google.genai import types
from agent.core_agent.plugins.ingestion.plugin import (
    GeminiEnterpriseFileIngestionPlugin,
)

pytestmark = pytest.mark.asyncio

# ─── Helpers ──────────────────────────────────────────────────────────────────


class FakeStorageService:
    def __init__(self, metadata=None):
        self.get_artifact_metadata = AsyncMock(return_value=metadata)
        self.get_artifact_version = AsyncMock(return_value=None)
        self.ensure_uploader_permissions = AsyncMock()


def _make_invocation_context(user_id="emmanuel.amador@endava.com"):
    ctx = MagicMock()
    ctx.app_name = "test-app"
    ctx.user_id = user_id
    ctx.session = MagicMock()
    ctx.session.id = "session-123"
    ctx.artifact_service = FakeStorageService()
    return ctx


def _make_user_message(texts):
    parts = [types.Part(text=t) for t in texts]
    msg = types.Content(role="user", parts=parts)
    return msg


def _make_binary_part(filename, data=b"fake", mime_type="application/pdf"):
    blob = types.Blob(data=data, mime_type=mime_type, display_name=filename)
    part = types.Part(inline_data=blob)
    return part


# ─── Discovery Tests ──────────────────────────────────────────────────────────


async def test_resolve_empty_ge_tag_via_gcs_discovery():
    """Should discover a pre-stashed file in GCS when only an empty tag is provided."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    ctx = _make_invocation_context()

    # Mock GCS Discovery finding the file (using correct key 'file_uri')
    ctx.artifact_service.get_artifact_metadata.return_value = {
        "file_uri": "gs://discovery-bucket/pre-stashed.pdf",
        "mime_type": "application/pdf",
    }

    # Message with only tags (no binary part)
    msg = _make_user_message(
        [
            "\n<start_of_user_uploaded_file: pre-stashed.pdf>\n\n",
            "<end_of_user_uploaded_file: pre-stashed.pdf>\n",
        ]
    )

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is not None
    # Verify discovery was called
    ctx.artifact_service.get_artifact_metadata.assert_called_once_with(
        filename="pre-stashed.pdf",
        user_id="emmanuel.amador@endava.com",
        app_name="test-app",
        session_id="session-123",
    )

    # Verify IAM permissions were ensured for the discovered file
    ctx.artifact_service.ensure_uploader_permissions.assert_called_once_with(
        "gs://discovery-bucket/pre-stashed.pdf",
        "emmanuel.amador@endava.com",
        "test-app",
    )

    # Verify the result contains the file_data part
    file_data_parts = [p for p in result.parts if getattr(p, "file_data", None)]
    assert len(file_data_parts) == 1
    assert (
        file_data_parts[0].file_data.file_uri == "gs://discovery-bucket/pre-stashed.pdf"
    )
    assert file_data_parts[0].file_data.mime_type == "application/pdf"


async def test_resolve_tag_via_turn_registry_precedence():
    """Should use the registry (from current turn) instead of GCS discovery when possible."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    ctx = _make_invocation_context()

    # Mock save_artifact returning a URI
    ctx.artifact_service.save_artifact = AsyncMock(return_value=1)
    mock_version = MagicMock()
    mock_version.canonical_uri = "gs://registry-bucket/new-file.pdf"
    mock_version.mime_type = "application/pdf"
    ctx.artifact_service.get_artifact_version = AsyncMock(return_value=mock_version)

    # Message with binary part AND tags
    binary_part = _make_binary_part("new-file.pdf")
    tag_part_start = types.Part(
        text="\n<start_of_user_uploaded_file: new-file.pdf>\n\n"
    )
    tag_part_end = types.Part(text="<end_of_user_uploaded_file: new-file.pdf>\n")

    msg = types.Content(role="user", parts=[binary_part, tag_part_start, tag_part_end])

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    # Verify save was called for the binary part
    ctx.artifact_service.save_artifact.assert_called_once()

    # Verify discovery was NOT called (registry hit)
    ctx.artifact_service.get_artifact_metadata.assert_not_called()

    # Check that both locations (where binary was and where tag was) resolved to the same URI
    file_data_parts = [p for p in result.parts if getattr(p, "file_data", None)]
    assert len(file_data_parts) == 2
    for p in file_data_parts:
        assert p.file_data.file_uri == "gs://registry-bucket/new-file.pdf"


async def test_handle_discovery_failure_gracefully():
    """Should return a descriptive error placeholder when a tag cannot be resolved."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    ctx = _make_invocation_context()

    # Mock discovery failure (returns None)
    ctx.artifact_service.get_artifact_metadata.return_value = None

    msg = _make_user_message(
        [
            "\n<start_of_user_uploaded_file: missing.pdf>\n\n",
            "<end_of_user_uploaded_file: missing.pdf>\n",
        ]
    )

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    # Should resolve to an error text part
    error_parts = [
        p
        for p in result.parts
        if getattr(p, "text", None) and "[Empty/Non-text Artifact" in p.text
    ]
    assert len(error_parts) == 1
    assert "missing.pdf" in error_parts[0].text


async def test_identity_management_skipped_when_user_id_missing():
    """Should skip discovery and IAM grants when no user_id is present in context."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    ctx = _make_invocation_context(user_id=None)

    msg = _make_user_message(
        [
            "\n<start_of_user_uploaded_file: contract.pdf>\n\n",
            "<end_of_user_uploaded_file: contract.pdf>\n",
        ]
    )

    await plugin.on_user_message_callback(invocation_context=ctx, user_message=msg)

    # Verify discovery was NOT called because user_id is missing
    ctx.artifact_service.get_artifact_metadata.assert_not_called()
    ctx.artifact_service.ensure_uploader_permissions.assert_not_called()


async def test_mime_type_integrity_in_discovery():
    """Should correctly propagate non-default MIME types from GCS discovery."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    ctx = _make_invocation_context()

    ctx.artifact_service.get_artifact_metadata.return_value = {
        "file_uri": "gs://discovery-bucket/photo.jpg",
        "mime_type": "image/jpeg",
    }

    msg = _make_user_message(
        [
            "\n<start_of_user_uploaded_file: photo.jpg>\n\n",
            "<end_of_user_uploaded_file: photo.jpg>\n",
        ]
    )

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    file_data_parts = [p for p in result.parts if getattr(p, "file_data", None)]
    assert len(file_data_parts) == 1
    assert file_data_parts[0].file_data.mime_type == "image/jpeg"
