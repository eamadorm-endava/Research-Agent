"""Exercise the actual Streamlit chat request and unauthorized-response handling."""

from io import BytesIO
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests
from streamlit.runtime.context import ContextProxy, StreamlitHeaders
from streamlit.delta_generator import DeltaGenerator
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
        assert not app.get("iframe")
        assert app.status[0].label == "Loading…"
        assert post.call_count == 1
        app.run()
    assert not app.exception
    assert not app.get("iframe")
    assert app.session_state.pending_prompt is None
    assert app.session_state.session_id == "test-session"
    assert post.call_count == 2
    assert post.call_args.kwargs["json"]["message"] == "Original question"
    assert len(app.session_state.messages) == 2


@pytest.mark.parametrize("response_ids", ["missing", "names", "ids"])
def test_execution_history_survives_final_response_and_rerun(
    browser_identity, monkeypatch, response_ids
):
    calls = [
        {"name": "search_documents", "args": {}},
        {"name": "load_skill", "args": {"skill_name": "document_search"}},
        {"name": "search_documents", "args": {}},
    ]
    if response_ids == "ids":
        for index, call in enumerate(calls):
            call["id"] = str(index)
    parts = [{"functionCall": call} for call in calls]
    if response_ids != "missing":
        responses = reversed(calls) if response_ids == "ids" else calls
        parts.extend(
            {
                "functionResponse": {
                    "name": call["name"],
                    **({"id": call["id"]} if "id" in call else {}),
                }
            }
            for call in responses
        )
    parts.append({"text": "Finished."})
    response = MagicMock()
    response.__enter__.return_value = response
    response.iter_lines.return_value = [
        "data: "
        + json.dumps({"type": "agent_event", "payload": {"content": {"parts": [part]}}})
        for part in parts
    ]
    monkeypatch.setattr(requests, "post", MagicMock(return_value=response))
    app = AppTest.from_file(
        Path(__file__).resolve().parents[1] / "frontend" / "app.py"
    ).run()
    app.chat_input[0].set_value("Find a document").run()
    assert not app.exception
    message = app.session_state.messages[-1]
    assert message["content"] == "Finished."
    assert len(message["actions"]) == 3
    assert "Search Documents" in message["actions"][0]
    assert "Reading Skill Document Search" in message["actions"][1]
    assert "Search Documents" in message["actions"][2]
    app.run()
    assert not app.exception
    rendered = "\n".join(item.value for item in app.markdown)
    assert rendered.count("Search Documents") == 2
    assert "Reading Skill Document Search" in rendered
    assert "Finished." in rendered


@pytest.mark.parametrize(
    "start,end,label",
    [
        (100.0, 104.2, "Search Documents - 4.2s"),
        (100.0, 100.03, "Search Documents - <0.1s"),
        (None, None, "Search Documents"),
        (100.0, 100.0, "Search Documents"),
        (104.2, 100.0, "Search Documents"),
    ],
)
def test_tool_duration_uses_agent_timestamps_for_buffered_events(
    browser_identity, monkeypatch, start, end, label
):
    events = [
        {
            "timestamp": start,
            "content": {
                "parts": [
                    {
                        "functionCall": {
                            "id": "call-1",
                            "name": "search_documents",
                            "args": {},
                        }
                    }
                ]
            },
        },
        {
            "timestamp": end,
            "content": {
                "parts": [
                    {"functionResponse": {"id": "call-1", "name": "search_documents"}}
                ]
            },
        },
        {"content": {"parts": [{"text": "Finished."}]}},
    ]
    response = MagicMock()
    response.__enter__.return_value = response
    response.iter_lines.return_value = [
        "data: " + json.dumps({"type": "agent_event", "payload": event})
        for event in events
    ]
    monkeypatch.setattr(requests, "post", MagicMock(return_value=response))
    app = AppTest.from_file(
        Path(__file__).resolve().parents[1] / "frontend" / "app.py"
    ).run()
    app.chat_input[0].set_value("Find a document").run()
    assert not app.exception
    action = app.session_state.messages[-1]["actions"][0]
    assert f">{label}</span>" in action
    assert " - 0.0s" not in action
    if start == 100.0 and end == 104.2:
        assert app.session_state.messages[-1]["status_label"] == "Executed in 4 s"


def test_tool_name_and_spinner_remain_until_its_response(browser_identity, monkeypatch):
    rendered = []
    markdown = DeltaGenerator.markdown

    def record_markdown(self, body, *args, **kwargs):
        rendered.append(body)
        return markdown(self, body, *args, **kwargs)

    monkeypatch.setattr(DeltaGenerator, "markdown", record_markdown)
    events = [
        {
            "timestamp": 100,
            "content": {
                "parts": [
                    {
                        "functionCall": {
                            "id": "time-1",
                            "name": "get_current_time",
                            "args": {},
                        }
                    }
                ]
            },
        },
        {
            "timestamp": 102,
            "content": {
                "parts": [
                    {"functionResponse": {"id": "time-1", "name": "get_current_time"}}
                ]
            },
        },
        {"content": {"parts": [{"text": "Finished."}]}},
    ]
    response = MagicMock()
    response.__enter__.return_value = response
    response.iter_lines.return_value = [
        "data: " + json.dumps({"type": "agent_event", "payload": event})
        for event in events
    ]
    monkeypatch.setattr(requests, "post", MagicMock(return_value=response))
    app = AppTest.from_file(
        Path(__file__).resolve().parents[1] / "frontend" / "app.py"
    ).run()
    app.chat_input[0].set_value("What time is it?").run()
    assert not app.exception
    pending = next(body for body in rendered if "Get Current Time" in body)
    assert 'class="spin-icon"' in pending
    completed = app.session_state.messages[-1]["actions"][0]
    assert "Get Current Time - 2.0s" in completed
    assert "spin-icon" not in completed
