import pytest
from unittest.mock import AsyncMock, MagicMock

from google.genai import types

from agent.core_agent.plugins.artifacts.callbacks import (
    PENDING_RENDER_KEY,
    render_pending_artifacts,
)


def _make_callback_context(state: dict) -> MagicMock:
    """Builds a minimal CallbackContext mock with a writable state dict."""
    ctx = MagicMock()
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


@pytest.mark.asyncio
async def test_render_pending_artifacts_returns_all_parts_for_multiple_queued_artifacts():
    """Should load all queued artifacts and return Content with multiple Parts."""
    part_a = _make_part("image/png")
    part_b = _make_part("application/pdf")
    state = {PENDING_RENDER_KEY: ["image.png", "report.pdf"]}
    ctx = _make_callback_context(state)
    ctx.load_artifact = AsyncMock(side_effect=[part_a, part_b])

    result = await render_pending_artifacts(ctx)

    assert result is not None
    assert len(result.parts) == 2
    assert result.parts[0] is part_a
    assert result.parts[1] is part_b


@pytest.mark.asyncio
async def test_render_pending_artifacts_clears_queue_from_state_after_execution():
    """Should reset the render queue to an empty list after processing."""
    state = {PENDING_RENDER_KEY: ["file.png"]}
    ctx = _make_callback_context(state)
    ctx.load_artifact = AsyncMock(return_value=_make_part())

    await render_pending_artifacts(ctx)

    ctx.state.__setitem__.assert_called_with(PENDING_RENDER_KEY, [])


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_render_pending_artifacts_returns_none_when_queue_is_empty():
    """Should return None immediately when no artifacts are queued in state."""
    state = {}
    ctx = _make_callback_context(state)
    ctx.load_artifact = AsyncMock()

    result = await render_pending_artifacts(ctx)

    assert result is None
    ctx.load_artifact.assert_not_called()


@pytest.mark.asyncio
async def test_render_pending_artifacts_returns_none_when_queue_key_is_empty_list():
    """Should return None when the queue key exists but holds an empty list."""
    state = {PENDING_RENDER_KEY: []}
    ctx = _make_callback_context(state)
    ctx.load_artifact = AsyncMock()

    result = await render_pending_artifacts(ctx)

    assert result is None
    ctx.load_artifact.assert_not_called()


@pytest.mark.asyncio
async def test_render_pending_artifacts_skips_artifacts_that_load_as_none():
    """Should exclude artifacts that load_artifact returns None for."""
    real_part = _make_part()
    state = {PENDING_RENDER_KEY: ["missing.pdf", "found.png"]}
    ctx = _make_callback_context(state)
    ctx.load_artifact = AsyncMock(side_effect=[None, real_part])

    result = await render_pending_artifacts(ctx)

    assert result is not None
    assert len(result.parts) == 1
    assert result.parts[0] is real_part


@pytest.mark.asyncio
async def test_render_pending_artifacts_returns_none_when_all_artifacts_are_missing():
    """Should return None if every queued artifact fails to load."""
    state = {PENDING_RENDER_KEY: ["gone_a.pdf", "gone_b.pdf"]}
    ctx = _make_callback_context(state)
    ctx.load_artifact = AsyncMock(return_value=None)

    result = await render_pending_artifacts(ctx)

    assert result is None


# ---------------------------------------------------------------------------
# Failure Modes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_render_pending_artifacts_skips_artifact_that_raises_exception():
    """Should skip an artifact that raises during load and continue with remaining ones."""
    good_part = _make_part()
    state = {PENDING_RENDER_KEY: ["corrupt.pdf", "good.png"]}
    ctx = _make_callback_context(state)
    ctx.load_artifact = AsyncMock(side_effect=[RuntimeError("GCS error"), good_part])

    result = await render_pending_artifacts(ctx)

    assert result is not None
    assert len(result.parts) == 1
    assert result.parts[0] is good_part


@pytest.mark.asyncio
async def test_render_pending_artifacts_returns_none_when_all_artifacts_raise():
    """Should return None without propagating exceptions if all loads fail."""
    state = {PENDING_RENDER_KEY: ["bad_a.pdf", "bad_b.pdf"]}
    ctx = _make_callback_context(state)
    ctx.load_artifact = AsyncMock(side_effect=RuntimeError("GCS unavailable"))

    result = await render_pending_artifacts(ctx)

    assert result is None
