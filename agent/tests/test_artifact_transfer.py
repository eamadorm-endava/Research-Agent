from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent.core_agent.tools.artifact_transfer import _load_uploaded_artifact


@pytest.mark.asyncio
async def test_load_uploaded_artifact_uses_pending_delta_when_list_is_empty():
    tool_context = SimpleNamespace(
        state={
            "latest_uploaded_artifacts": ["uploaded.pdf"],
            "save_files_as_artifacts_plugin:pending_delta": {"uploaded.pdf": 0},
        },
        list_artifacts=AsyncMock(return_value=[]),
        load_artifact=AsyncMock(return_value=SimpleNamespace(inline_data=object())),
    )

    artifact_name, artifact_part = await _load_uploaded_artifact(tool_context, None)

    assert artifact_name == "uploaded.pdf"
    assert artifact_part is not None
    tool_context.load_artifact.assert_awaited_once_with("uploaded.pdf")


@pytest.mark.asyncio
async def test_load_uploaded_artifact_falls_back_across_known_candidates():
    artifact_part = SimpleNamespace(inline_data=object())
    tool_context = SimpleNamespace(
        state={
            "latest_uploaded_artifacts": ["stale.pdf", "fresh.pdf"],
            "save_files_as_artifacts_plugin:pending_delta": {"fresh.pdf": 1},
        },
        list_artifacts=AsyncMock(return_value=[]),
        load_artifact=AsyncMock(side_effect=[None, artifact_part]),
    )

    artifact_name, loaded_part = await _load_uploaded_artifact(tool_context, None)

    assert artifact_name == "fresh.pdf"
    assert loaded_part is artifact_part
    assert tool_context.load_artifact.await_count == 2


# @pytest.mark.asyncio
# async def test_load_uploaded_artifact_raises_when_nothing_is_known():
#     tool_context = SimpleNamespace(
#         state={},
#         list_artifacts=AsyncMock(return_value=[]),
#         load_artifact=AsyncMock(return_value=None),
#     )
