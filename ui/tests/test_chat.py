"""Exercise streaming, session isolation and honest availability reporting."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from ui.backend import agent_client
from ui.backend.routers import chat


@pytest.fixture
def remote(monkeypatch):
    async def stream(**kwargs):
        yield {"content": {"parts": [{"text": "Hello"}]}}

    remote = SimpleNamespace(
        async_create_session=AsyncMock(return_value={"id": "session-1"}),
        async_get_session=AsyncMock(return_value={"user_id": "alice@example.com"}),
        async_stream_query=stream,
    )
    monkeypatch.setattr(chat, "get_remote_agent", lambda: remote)
    return remote


def test_chat_does_not_require_all_providers(client, remote):
    response = client.post("/api/chat/", json={"message": "Hello"})
    assert response.status_code == 200
    assert '"type": "done"' in response.text
    assert "AUTH_REQUIRED" not in response.text
    remote.async_create_session.assert_awaited_once_with(user_id="alice@example.com")


def test_session_is_verified_before_reuse(client, remote):
    assert (
        client.post(
            "/api/chat/", json={"message": "Hello", "session_id": "session-1"}
        ).status_code
        == 200
    )
    remote.async_get_session.assert_awaited_once_with(
        user_id="alice@example.com", session_id="session-1"
    )


def test_cannot_reuse_another_users_session(client, remote):
    remote.async_get_session.return_value = {"user_id": "bob@example.com"}
    response = client.post(
        "/api/chat/", json={"message": "Hello", "session_id": "stolen"}
    )
    assert response.status_code == 403


def test_empty_message_is_rejected(client):
    assert client.post("/api/chat/", json={"message": ""}).status_code == 422


def test_readiness_returns_unavailable_when_engine_missing(client, monkeypatch):
    monkeypatch.setattr(
        "ui.backend.main.get_remote_agent",
        MagicMock(side_effect=HTTPException(503, "Unavailable")),
    )
    assert client.get("/api/ready").status_code == 503
    assert client.get("/health").json() == {"status": "alive"}


def test_engine_resolution_retries_after_failed_lookup(config, monkeypatch):
    agent_client.get_remote_agent.cache_clear()
    monkeypatch.setattr(agent_client.vertexai, "init", lambda **_: None)
    monkeypatch.setattr(config, "AGENT_RESOURCE_NAME", "")
    monkeypatch.setattr(config, "AGENT_DISPLAY_NAME", "OSIRIS")
    agents = []
    monkeypatch.setattr(agent_client.agent_engines, "list", lambda: agents)
    with pytest.raises(HTTPException):
        agent_client.get_remote_agent()
    engine = SimpleNamespace(api_resource=SimpleNamespace(display_name="OSIRIS"))
    agents.append(engine)
    assert agent_client.get_remote_agent() is engine
    agent_client.get_remote_agent.cache_clear()


def test_missing_session_does_not_start_another_users_run(client, remote):
    remote.async_get_session.side_effect = RuntimeError("Session not found")
    assert (
        client.post(
            "/api/chat/", json={"message": "Hello", "session_id": "missing"}
        ).status_code
        == 404
    )


def test_failed_stream_has_error_and_no_completion_event(client, remote, monkeypatch):
    async def failed_stream(**kwargs):
        yield {"content": {"parts": [{"text": "partial"}]}}
        raise RuntimeError("private provider error")

    remote.async_stream_query = failed_stream
    getter = MagicMock(return_value=remote)
    monkeypatch.setattr(chat, "get_remote_agent", getter)
    response = client.post("/api/chat/", json={"message": "Hello"})
    assert '"type": "error"' in response.text
    assert '"type": "done"' not in response.text
    assert "private provider error" not in response.text
    getter.cache_clear.assert_called_once()
