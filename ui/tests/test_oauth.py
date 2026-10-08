"""Exercise browser-bound single-use consent without external token calls."""

from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import HTTPException

from ui.backend import oauth_state
from ui.backend.routers import oauth


def start_consent(client, provider="google", connect_all=False):
    response = client.get(
        f"/api/auth/{provider}/login?connect_all={str(connect_all).lower()}",
        follow_redirects=False,
    )
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
    transaction = oauth_state.create_state(
        "alice@example.com", "google", "test-browser-session"
    )
    state, browser = transaction["state"], "test-browser-session"
    with pytest.raises(HTTPException) as failure:
        oauth_state.consume_state(state, browser, user, provider)
    assert failure.value.status_code == 400


def test_expired_state_cannot_be_used(database, config):
    transaction = oauth_state.create_state(
        "alice@example.com", "google", "test-browser-session"
    )
    state, browser = transaction["state"], "test-browser-session"
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


@pytest.mark.parametrize(
    "provider,name,path",
    [
        ("google", "oauth_google", "/api/auth/google"),
        ("microsoft", "oauth_microsoft", "/api/auth/microsoft"),
        ("atlassian", "oauth_atlassian", "/api/auth/atlassian"),
    ],
)
def test_consent_cookie_uses_fixed_metadata_and_random_value(
    client, provider, name, path
):
    _, _, response = start_consent(client, provider)
    cookie = SimpleCookie(response.headers["set-cookie"])
    assert set(cookie) == {name}
    assert cookie[name]["path"] == path
    assert cookie[name]["httponly"] is True
    assert cookie[name]["secure"] is True
    assert len(cookie[name].value) == 32
    assert all(character in "0123456789abcdef" for character in cookie[name].value)
    _, _, second_response = start_consent(client, provider)
    assert (
        SimpleCookie(second_response.headers["set-cookie"])[name].value
        != cookie[name].value
    )


@pytest.mark.parametrize(
    "provider",
    ["unknown", "google;HttpOnly=false", "google%0d%0aSet-Cookie:injected=yes"],
)
def test_invalid_provider_cannot_create_a_cookie(client, provider):
    response = client.get(f"/api/auth/{provider}/login", follow_redirects=False)
    assert response.status_code == 400
    assert "set-cookie" not in response.headers


def test_callback_removes_cookie_with_the_same_fixed_metadata(client, monkeypatch):
    state, _, _ = start_consent(client, "microsoft")
    monkeypatch.setattr(
        oauth,
        "exchange_tokens",
        lambda *args: oauth.TokenData(access_token="token", expires_at=3600),
    )
    response = client.get(f"/api/auth/microsoft/callback?state={state}&code=valid")
    assert response.status_code == 200
    cookie = SimpleCookie(response.headers["set-cookie"])
    assert set(cookie) == {"oauth_microsoft"}
    assert cookie["oauth_microsoft"]["path"] == "/api/auth/microsoft"
    assert cookie["oauth_microsoft"]["max-age"] == "0"


def test_cookie_contains_only_session_id_and_not_provider_secrets(client, database):
    _, _, response = start_consent(client)
    cookie_value = SimpleCookie(response.headers["set-cookie"])["oauth_google"].value
    transaction = next(iter(database.records.values()))
    assert cookie_value == transaction["browser_session_id"]
    assert cookie_value != transaction["verifier"]
    assert "access_token" not in cookie_value
    assert "refresh_token" not in cookie_value
    assert "test-secret" not in cookie_value


def test_callback_rejects_cookie_from_another_browser(client, monkeypatch):
    state, _, _ = start_consent(client)
    monkeypatch.setattr(
        oauth.requests,
        "post",
        lambda *args, **kwargs: pytest.fail("Token exchange must not run"),
    )
    response = client.get(
        f"/api/auth/google/callback?state={state}&code=valid",
        headers={"Cookie": "oauth_google=00000000000000000000000000000000"},
    )
    assert response.status_code == 400


def test_callback_rejects_state_created_before_session_id_change(client, database):
    state, _, _ = start_consent(client)
    transaction = next(iter(database.records.values()))
    transaction.pop("browser_session_id")
    transaction["browser_digest"] = "legacy-cookie-digest"
    response = client.get(f"/api/auth/google/callback?state={state}&code=valid")
    assert response.status_code == 400
