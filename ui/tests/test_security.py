"""Check the browser and request boundaries required by cybersecurity-guide."""


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
