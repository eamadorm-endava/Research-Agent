"""Check server-confirmed readiness and consent chaining without browser guesses."""

import time
from urllib.parse import parse_qs, urlsplit

from ui.backend.auth import get_current_user
from ui.backend.routers import oauth
from ui.tests.test_oauth import start_consent


def test_status_lists_only_the_current_users_missing_connections(client):
    token = oauth.TokenData(access_token="private-token", expires_at=time.time() + 3600)
    oauth.token_store.save_tokens("bob@example.com", "google", token)
    assert client.get("/api/auth/status").json() == {
        "missing_providers": ["google", "microsoft", "atlassian"]
    }
    oauth.token_store.save_tokens("alice@example.com", "google", token)
    response = client.get("/api/auth/status")
    assert response.json() == {"missing_providers": ["microsoft", "atlassian"]}
    assert "private-token" not in response.text


def test_status_does_not_accept_expired_credentials(client):
    oauth.token_store.save_tokens(
        "alice@example.com",
        "google",
        oauth.TokenData(access_token="expired", expires_at=1),
    )
    assert "google" in client.get("/api/auth/status").json()["missing_providers"]


def test_status_requires_signed_user_identity(client):
    client.app.dependency_overrides.pop(get_current_user)
    assert client.get("/api/auth/status").status_code == 401


def test_one_consent_flow_chains_all_providers_then_closes(client, monkeypatch):
    monkeypatch.setattr(
        oauth,
        "exchange_tokens",
        lambda *args: oauth.TokenData(
            access_token="private-token", expires_at=time.time() + 3600
        ),
    )
    state, _, _ = start_consent(client, connect_all=True)
    providers = ["google", "microsoft", "atlassian"]
    for index, provider in enumerate(providers):
        response = client.get(
            f"/api/auth/{provider}/callback?state={state}&code=valid",
            follow_redirects=False,
        )
        assert client.get("/api/auth/status").json() == {
            "missing_providers": providers[index + 1 :]
        }
        if index < 2:
            assert response.status_code == 307
            assert response.headers["location"] == (
                f"https://osiris.example.com/api/auth/{providers[index + 1]}/login"
                "?connect_all=true"
            )
            consent = client.get(response.headers["location"], follow_redirects=False)
            state = parse_qs(urlsplit(consent.headers["location"]).query)["state"][0]
        else:
            assert response.status_code == 200
            assert "window.close()" in response.text
            assert "private-token" not in response.text


def test_denied_consent_never_advances_connection_flow(client):
    state, _, _ = start_consent(client, connect_all=True)
    response = client.get(
        f"/api/auth/google/callback?state={state}&error=access_denied",
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert client.get("/api/auth/status").json() == {
        "missing_providers": ["google", "microsoft", "atlassian"]
    }
