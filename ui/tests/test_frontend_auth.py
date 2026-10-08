"""Exercise the actual Streamlit chat request and unauthorized-response handling."""

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests
from streamlit.runtime.context import ContextProxy, StreamlitHeaders
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("status_code", [200, 401])
def test_chat_forwards_assertion_separately_from_service_token(
    monkeypatch, status_code
):
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
    response = MagicMock(status_code=status_code)
    response.__enter__.return_value = response
    response.iter_lines.return_value = [
        'data: {"type": "AUTH_REQUIRED", "missing_providers": ["google"]}'
    ]
    if status_code == 401:
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
    post = MagicMock(return_value=response)
    monkeypatch.setattr(requests, "post", post)
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
        assert "Connect **Google**" in app.warning[0].value
