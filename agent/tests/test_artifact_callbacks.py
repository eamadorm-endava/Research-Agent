import pytest
from unittest.mock import AsyncMock, MagicMock

from google.genai import types

from agent.core_agent.artifact_management.schemas import (
    PENDING_RENDER_KEY,
    PENDING_URI_KEY,
)
from agent.core_agent.callbacks.artifact_rendering import (
    render_pending_artifacts,
)


def _make_callback_context(state: dict) -> MagicMock:
    """Builds a minimal CallbackContext mock with a writable state dict."""
    ctx = MagicMock()
    # Explicitly clear invocation_context attributes to avoid MagicMock fall-through
    ctx.invocation_context = MagicMock()
    ctx.invocation_context.artifact_service = None

    ctx.state = MagicMock()
    ctx.state.get = MagicMock(
        side_effect=lambda key, default=None: state.get(key, default)
    )
    ctx.state.__setitem__ = MagicMock(
        side_effect=lambda key, value: state.update({key: value})
    )
    return ctx


def _make_part(mime_type: str = "image/png") -> types.Part:
    return types.Part(inline_data=types.Blob(data=b"fake", mime_type=mime_type))


# ---------------------------------------------------------------------------
# Happy Path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_render_pending_artifacts_returns_content_for_single_queued_artifact():
    """Should load one artifact and return Content with one Part."""
    expected_part = _make_part()
    state = {PENDING_RENDER_KEY: ["report.pdf"]}
    ctx = _make_callback_context(state)
    ctx.load_artifact = AsyncMock(return_value=expected_part)

    result = await render_pending_artifacts(ctx)

    assert result is not None
    assert isinstance(result, types.Content)
    assert result.role == "model"
    assert len(result.parts) == 1
    assert result.parts[0] is expected_part
    assert state[PENDING_RENDER_KEY] == []


@pytest.mark.asyncio
async def test_render_pending_artifacts_returns_content_for_direct_gcs_uri():
    """Should process an external GCS URI and return Content with a file_data Part."""
    state = {
        PENDING_URI_KEY: [
            {"uri": "gs://bucket/file.pdf", "mime_type": "application/pdf"}
        ]
    }
    ctx = _make_callback_context(state)

    result = await render_pending_artifacts(ctx)

    assert result is not None
    assert len(result.parts) == 1
    assert result.parts[0].file_data.file_uri == "gs://bucket/file.pdf"
    assert result.parts[0].file_data.mime_type == "application/pdf"
    assert state[PENDING_URI_KEY] == []


@pytest.mark.asyncio
async def test_render_pending_artifacts_merges_local_and_external_content():
    """Should combine both local artifacts and external GCS URIs in the same turn."""
    local_part = _make_part("image/png")
    state = {
        PENDING_RENDER_KEY: ["local.png"],
        PENDING_URI_KEY: [
            {"uri": "gs://bucket/remote.pdf", "mime_type": "application/pdf"}
        ],
    }
    ctx = _make_callback_context(state)
    ctx.load_artifact = AsyncMock(return_value=local_part)

    result = await render_pending_artifacts(ctx)

    assert result is not None
    assert len(result.parts) == 2
    # Local artifact part
    assert result.parts[0] is local_part
    # External URI part
    assert result.parts[1].file_data.file_uri == "gs://bucket/remote.pdf"

    assert state[PENDING_RENDER_KEY] == []
    assert state[PENDING_URI_KEY] == []


@pytest.mark.asyncio
async def test_render_pending_artifacts_clears_queues_even_if_partial_failure():
    """Should reset all render queues even if some items fail to load."""
    state = {
        PENDING_RENDER_KEY: ["missing.png"],
        PENDING_URI_KEY: [{"uri": "gs://bucket/valid.pdf"}],
    }
    ctx = _make_callback_context(state)
    ctx.load_artifact = AsyncMock(return_value=None)

    result = await render_pending_artifacts(ctx)

    assert result is not None
    assert len(result.parts) == 1
    assert result.parts[0].file_data.file_uri == "gs://bucket/valid.pdf"
    assert state[PENDING_RENDER_KEY] == []
    assert state[PENDING_URI_KEY] == []


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_render_pending_artifacts_returns_none_when_all_queues_empty():
    """Should return None immediately when no content is queued in any state key."""
    state = {}
    ctx = _make_callback_context(state)
    ctx.load_artifact = AsyncMock()

    result = await render_pending_artifacts(ctx)

    assert result is None
    ctx.load_artifact.assert_not_called()


@pytest.mark.asyncio
async def test_render_pending_artifacts_handles_missing_uri_fields_gracefully():
    """Should skip malformed external URI entries without crashing."""
    state = {
        PENDING_URI_KEY: [
            {"uri": "gs://valid/file.pdf"},  # Valid
            {"mime_type": "application/pdf"},  # Missing URI
            {},  # Empty
        ]
    }
    ctx = _make_callback_context(state)

    result = await render_pending_artifacts(ctx)

    assert result is not None
    assert len(result.parts) == 1
    assert result.parts[0].file_data.file_uri == "gs://valid/file.pdf"
