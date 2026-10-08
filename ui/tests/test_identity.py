"""Regression tests for forged headers and IAP JWT trust boundaries."""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from starlette.requests import Request

from ui.backend import auth

AUDIENCE = "/projects/123/global/backendServices/456"


@pytest.fixture
def signing_key(monkeypatch):
    private_key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(
        auth.IAP_KEYS,
        "get_signing_key_from_jwt",
        lambda _: SimpleNamespace(key=private_key.public_key()),
    )
    monkeypatch.setattr(auth, "expected_audiences", lambda: (AUDIENCE,))
    return private_key


def assertion(signing_key, **overrides):
    now = int(time.time())
    claims = {
        "sub": "user-1",
        "email": "alice@example.com",
        "aud": AUDIENCE,
        "iss": auth.IAP_ISSUER,
        "iat": now,
        "exp": now + 600,
    }
    claims.update(overrides)
    return jwt.encode(claims, signing_key, algorithm="ES256")


def test_valid_signed_identity(signing_key):
    assert auth.verify_assertion(assertion(signing_key)) == "alice@example.com"


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "another-backend"},
        {"iss": "https://attacker.example"},
        {"exp": 1},
        {"iat": int(time.time()) + 1000},
        {"exp": int(time.time()) + 10000},
        {"email": ""},
    ],
)
def test_rejects_invalid_claims(signing_key, overrides):
    with pytest.raises(jwt.PyJWTError):
        auth.verify_assertion(assertion(signing_key, **overrides))


def test_unsigned_email_header_does_not_authenticate(config):
    request = Request(
        {
            "type": "http",
            "headers": [(b"x-goog-authenticated-user-email", b"alice@example.com")],
        }
    )
    with pytest.raises(HTTPException) as failure:
        auth.get_current_user(request)
    assert failure.value.status_code == 401


def test_development_identity_requires_explicit_opt_in(config, monkeypatch):
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    monkeypatch.setattr(config, "LOCAL_USER_EMAIL", "local@example.com")
    assert (
        auth.get_current_user(Request({"type": "http", "headers": []}))
        == "local@example.com"
    )
