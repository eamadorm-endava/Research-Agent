"""Upload signing and frontend stream parsing regressions."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ui.backend.routers import upload
from ui.frontend import client as frontend


def test_signed_upload_is_private_bounded_and_uses_adc(client, monkeypatch):
    credentials = MagicMock(token="adc-token")
    monkeypatch.setattr(
        upload.google.auth, "default", lambda **_: (credentials, "project")
    )
    blob = MagicMock()
    blob.generate_signed_url.return_value = "https://storage.example/signed"
    storage = MagicMock()
    storage.bucket.return_value.blob.return_value = blob
    monkeypatch.setattr(upload.storage, "Client", lambda **_: storage)
    response = client.post(
        "/api/upload/generate-url",
        json={
            "filename": "report.pdf",
            "content_type": "application/pdf",
            "size_bytes": 123,
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["url"] == "https://storage.example/signed"
    assert result["gcs_uri"].startswith("gs://private-uploads/uploads/")
    assert "alice@example.com" not in result["gcs_uri"]
    kwargs = blob.generate_signed_url.call_args.kwargs
    assert kwargs["headers"] == {"Content-Length": "123"}
    assert kwargs["method"] == "PUT"
    assert kwargs["access_token"] == "adc-token"


@pytest.mark.parametrize(
    "body,status",
    [
        (
            {
                "filename": "../report.pdf",
                "content_type": "application/pdf",
                "size_bytes": 1,
            },
            422,
        ),
        (
            {
                "filename": "report.pdf",
                "content_type": "application/pdf",
                "size_bytes": 0,
            },
            422,
        ),
        (
            {
                "filename": "report.pdf",
                "content_type": "application/pdf",
                "size_bytes": 30_000_000,
            },
            413,
        ),
        (
            {"filename": "report.html", "content_type": "text/html", "size_bytes": 10},
            415,
        ),
    ],
)
def test_invalid_uploads_are_rejected(client, body, status):
    assert client.post("/api/upload/generate-url", json=body).status_code == status


def test_frontend_forwarding_keeps_user_and_service_tokens_separate(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(frontend, "API_URL", "https://backend.run.app/api")

    class Response:
        def __enter__(self):
            return SimpleNamespace(read=lambda: b"service-token")

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(
        frontend.urllib.request, "urlopen", lambda *args, **kwargs: Response()
    )
    assert frontend.request_headers("iap-assertion") == {
        "X-Goog-IAP-JWT-Assertion": "iap-assertion",
        "Authorization": "Bearer service-token",
    }
    with pytest.raises(RuntimeError):
        frontend.request_headers(None)


def test_frontend_parser_excludes_thoughts_and_preserves_tools():
    payload = {
        "content": {
            "parts": [
                {"text": "secret", "thought": True},
                {"text": "answer"},
                {"function_call": {"name": "search_drive"}},
            ]
        }
    }
    assert frontend.extract_parts(payload) == ("answer", ["search drive"])
    with pytest.raises(RuntimeError):
        frontend.extract_parts({"errorMessage": "private internal error"})
