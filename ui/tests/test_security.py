"""Check the browser and request boundaries required by cybersecurity-guide."""

from html.parser import HTMLParser


class ScriptParser(HTMLParser):
    """Extract script text from the callback HTML for its CSP assertion."""

    def __init__(self):
        super().__init__()
        self.in_script = False
        self.script_count = 0
        self.script_content = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.in_script = True
            self.script_count += 1

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False

    def handle_data(self, text):
        if self.in_script:
            self.script_content.append(text)


def test_response_sets_security_headers(client):
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["strict-transport-security"].startswith("max-age=")
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert "script-src 'sha256-" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"


def test_cors_rejects_unknown_origin(client):
    response = client.options(
        "/api/auth/google/login",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_allows_configured_origin(client):
    from fastapi.middleware.cors import CORSMiddleware

    from ui.backend.main import app

    middleware = next(
        item for item in app.user_middleware if item.cls is CORSMiddleware
    )
    origin = middleware.kwargs["allow_origins"][0]
    response = client.options(
        "/api/auth/google/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_rate_limit_rejects_excess_requests(client, monkeypatch):
    from ui.backend.config import UI_CONFIG
    from ui.backend.main import app

    monkeypatch.setattr(UI_CONFIG, "REQUESTS_PER_MINUTE", 1)
    app.state.limiter.reset()
    first = client.get("/api/auth/google/login", follow_redirects=False)
    second = client.get("/api/auth/google/login", follow_redirects=False)
    assert first.status_code == 307
    assert second.status_code == 429


def test_csp_fingerprint_matches_the_public_popup_script(client, monkeypatch):
    import base64
    import hashlib

    from ui.backend.config import OAUTH_CALLBACK_CSP_SOURCE
    from ui.backend.routers import oauth
    from ui.tests.test_oauth import start_consent

    state, _, _ = start_consent(client)
    monkeypatch.setattr(
        oauth,
        "exchange_tokens",
        lambda *args: oauth.TokenData(access_token="token", expires_at=3600),
    )
    response = client.get(f"/api/auth/google/callback?state={state}&code=valid")
    assert response.status_code == 200
    parser = ScriptParser()
    parser.feed(response.text)
    parser.close()
    assert parser.script_count == 1
    public_script_content = "".join(parser.script_content)
    expected_fingerprint = base64.b64encode(
        hashlib.sha256(public_script_content.encode()).digest()
    ).decode()
    assert OAUTH_CALLBACK_CSP_SOURCE == f"'sha256-{expected_fingerprint}'"
    assert (
        f"script-src {OAUTH_CALLBACK_CSP_SOURCE};"
        in response.headers["content-security-policy"]
    )
    assert "unsafe-inline" not in response.headers["content-security-policy"]
