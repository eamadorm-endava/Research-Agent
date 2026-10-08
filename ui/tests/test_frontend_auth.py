"""Exercise the actual Streamlit chat request and unauthorized-response handling."""

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests
from streamlit.runtime.context import ContextProxy, StreamlitHeaders
from streamlit.testing.v1 import AppTest


@pytest.fixture
def browser_identity(monkeypatch):
    monkeypatch.setattr(
        ContextProxy,
        "headers",
        property(
            lambda _: StreamlitHeaders(
                [("X-Goog-IAP-JWT-Assertion", "signed-user-assertion")]
            )
        ),
    )
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *args, **kwargs: BytesIO(b"service-id-token")
    )


@pytest.mark.parametrize("status_code", [200, 401])
def test_chat_forwards_assertion_separately_from_service_token(
    browser_identity, monkeypatch, status_code
):
    response = MagicMock(status_code=status_code)
    response.__enter__.return_value = response
    response.iter_lines.return_value = [
        'data: {"type": "AUTH_REQUIRED", "missing_providers": ["google"]}'
    ]
    if status_code == 401:
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
    post = MagicMock(return_value=response)
    monkeypatch.setattr(requests, "post", post)
    status_response = MagicMock()
    status_response.json.return_value = {"missing_providers": ["google"]}
    monkeypatch.setattr(requests, "get", MagicMock(return_value=status_response))
    app = AppTest.from_file(
        Path(__file__).resolve().parents[1] / "frontend" / "app.py"
    ).run()
    app.chat_input[0].set_value("Hello").run()
    assert not app.exception
    headers = post.call_args.kwargs["headers"]
    assert headers["X-Osiris-IAP-Assertion"] == "signed-user-assertion"
    assert headers["Authorization"] == "Bearer service-id-token"
    assert "X-Goog-IAP-JWT-Assertion" not in headers
    if status_code == 401:
        assert app.error[0].value == (
            "Your access session could not be verified. Reload this page and try again."
        )
        assert app.session_state.pending_prompt is None
    else:
        assert not app.warning
        assert not app.info
        assert not app.button
        assert app.chat_input[0].disabled
        assert "Google Workspace Connection" in app.get("iframe")[0].proto.srcdoc


def test_connections_advance_and_resume_the_original_message(
    browser_identity, monkeypatch
):
    missing = ["google", "microsoft", "atlassian"]
    status_response = MagicMock()
    status_response.json.side_effect = lambda: {"missing_providers": missing.copy()}
    monkeypatch.setattr(requests, "get", MagicMock(return_value=status_response))
    consent_response = MagicMock()
    consent_response.__enter__.return_value = consent_response
    consent_response.iter_lines.return_value = [
        'data: {"type": "AUTH_REQUIRED", "missing_providers": ["google", "microsoft", "atlassian"]}'
    ]
    agent_response = MagicMock()
    agent_response.__enter__.return_value = agent_response
    agent_response.iter_lines.return_value = [
        'data: {"type": "session_info", "session_id": "test-session"}',
        'data: {"type": "agent_event", "payload": "Done"}',
    ]
    post = MagicMock(side_effect=[consent_response, agent_response])
    monkeypatch.setattr(requests, "post", post)
    app = AppTest.from_file(
        Path(__file__).resolve().parents[1] / "frontend" / "app.py"
    ).run()
    app.chat_input[0].set_value("Original question").run()
    for label in ["Google Workspace", "Microsoft 365", "Atlassian"]:
        assert not app.exception
        assert f"{label} Connection" in app.get("iframe")[0].proto.srcdoc
        assert app.session_state.pending_prompt == "Original question"
        assert post.call_count == 1
        app.run()  # A poll with unchanged credentials never advances the flow.
        assert post.call_count == 1
        missing.pop(0)
        app.run()
    assert not app.exception
    assert not app.get("iframe")
    assert app.session_state.pending_prompt is None
    assert app.session_state.session_id == "test-session"
    assert post.call_count == 2
    assert post.call_args.kwargs["json"]["message"] == "Original question"
    assert len(app.session_state.messages) == 2
