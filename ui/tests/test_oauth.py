"""Exercise browser-bound single-use consent without external token calls."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import HTTPException

from ui.backend import oauth_state
from ui.backend.routers import oauth


def start_consent(client, provider="google"):
    response = client.get(f"/api/auth/{provider}/login", follow_redirects=False)
    assert response.status_code == 307
    params = parse_qs(urlsplit(response.headers["location"]).query)
    return params["state"][0], params, response


def test_callback_requires_browser_cookie_and_consumes_state(client, monkeypatch):
    state, params, response = start_consent(client)
    assert params["code_challenge_method"] == ["S256"]
    assert params["redirect_uri"] == [
        "https://osiris.example.com/api/auth/google/callback"
    ]
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
    post = []
    monkeypatch.setattr(
        oauth.requests,
        "post",
        lambda *args, **kwargs: (
            post.append(kwargs)
            or SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {
                    "access_token": "token",
                    "refresh_token": "refresh",
                    "expires_in": 3600,
                },
            )
        ),
    )
    response = client.get(f"/api/auth/google/callback?state={state}&code=valid")
    assert response.status_code == 200
    assert "code_verifier" in post[0]["data"]
    assert post[0]["timeout"] == 20
    assert (
        client.get(f"/api/auth/google/callback?state={state}&code=replay").status_code
        == 400
    )
    assert len(post) == 1


def test_forged_state_never_exchanges_code(client, monkeypatch):
    monkeypatch.setattr(
        oauth.requests,
        "post",
        lambda *args, **kwargs: pytest.fail("Unexpected token exchange"),
    )
    assert (
        client.get("/api/auth/google/callback?state=forged&code=bad").status_code == 400
    )


@pytest.mark.parametrize(
    "user,provider", [("bob@example.com", "google"), ("alice@example.com", "microsoft")]
)
def test_state_cannot_cross_users_or_providers(database, config, user, provider):
    state, browser, _ = oauth_state.create_state("alice@example.com", "google")
    with pytest.raises(HTTPException) as failure:
        oauth_state.consume_state(state, browser, user, provider)
    assert failure.value.status_code == 400


def test_expired_state_cannot_be_used(database, config):
    state, browser, _ = oauth_state.create_state("alice@example.com", "google")
    next(iter(database.records.values()))["expires_at"] = datetime.now(UTC) - timedelta(
        seconds=1
    )
    with pytest.raises(HTTPException):
        oauth_state.consume_state(state, browser, "alice@example.com", "google")


def test_provider_denial_is_consumed_without_saving_tokens(client):
    state, _, _ = start_consent(client)
    response = client.get(
        f"/api/auth/google/callback?state={state}&error=access_denied"
    )
    assert response.status_code == 400


def test_unknown_provider_and_missing_configuration_fail_closed(client, monkeypatch):
    assert client.get("/api/auth/unknown/login").status_code == 400
    monkeypatch.setattr(oauth.GOOGLE_AUTH_CONFIG, "CLIENT_SECRET", "mock-secret")
    assert client.get("/api/auth/google/login").status_code == 503
