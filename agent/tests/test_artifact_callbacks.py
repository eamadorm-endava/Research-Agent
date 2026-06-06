import pytest
from unittest.mock import AsyncMock, MagicMock

from google.genai import types

from agent.core_agent.artifact_management.schemas import (
    PENDING_UI_ARTIFACTS_QUEUE,
)
from agent.core_agent.callbacks.inject_local_artifacts import (
    inject_local_artifacts,
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
async def test_inject_local_artifacts_returns_content_for_single_queued_artifact():
    """Should load one artifact and return Content with one Part."""
    expected_part = _make_part()
    state = {PENDING_UI_ARTIFACTS_QUEUE: ["report.pdf"]}
    ctx = _make_callback_context(state)
    ctx.load_artifact = AsyncMock(return_value=expected_part)

    result = await inject_local_artifacts(ctx)

    assert result is not None
    assert isinstance(result, types.Content)
    assert result.role == "model"
    assert len(result.parts) == 1
    assert result.parts[0] is expected_part
    assert state[PENDING_UI_ARTIFACTS_QUEUE] == []


@pytest.mark.asyncio
async def test_inject_local_artifacts_returns_none_when_all_queues_empty():
    """Should return None immediately when no content is queued in any state key."""
    state = {}
    ctx = _make_callback_context(state)
    ctx.load_artifact = AsyncMock()

    result = await inject_local_artifacts(ctx)

    assert result is None
    ctx.load_artifact.assert_not_called()
