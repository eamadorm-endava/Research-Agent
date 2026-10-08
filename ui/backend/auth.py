"""Verify IAP assertions forwarded by Streamlit or received from the API NEG."""

import time

import google.auth
import jwt
from fastapi import HTTPException, Request
from google.auth.transport.requests import AuthorizedSession

from agent.core_agent.config import GCP_CONFIG

from .config import UI_CONFIG

IAP_ISSUER = "https://cloud.google.com/iap"
IAP_KEYS = jwt.PyJWKClient(
    "https://www.gstatic.com/iap/verify/public_key-jwk", timeout=10
)


def expected_audiences() -> tuple[str, ...]:
    """Resolve only configured backend names; never derive trust from token claims."""
    if UI_CONFIG.IAP_AUDIENCES:
        return tuple(UI_CONFIG.IAP_AUDIENCES)
    if not GCP_CONFIG.PROJECT_ID or not UI_CONFIG.PROJECT_NUMBER:
        raise RuntimeError("IAP project configuration is missing")
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    audiences = []
    with AuthorizedSession(credentials) as session:
        for name in UI_CONFIG.IAP_BACKEND_SERVICES:
            response = session.get(
                "https://compute.googleapis.com/compute/v1/projects/"
                f"{GCP_CONFIG.PROJECT_ID}/global/backendServices/{name}",
                timeout=10,
            )
            response.raise_for_status()
            audiences.append(
                f"/projects/{UI_CONFIG.PROJECT_NUMBER}/global/backendServices/"
                f"{response.json()['id']}"
            )
    if not audiences:
        raise RuntimeError("No trusted IAP backend services configured")
    return tuple(audiences)


def verify_assertion(assertion: str) -> str:
    """Check ES256 signature, configured audience, issuer, lifetime and user identity."""
    key = IAP_KEYS.get_signing_key_from_jwt(assertion).key
    claims = jwt.decode(
        assertion,
        key,
        algorithms=["ES256"],
        audience=expected_audiences(),
        issuer=IAP_ISSUER,
        leeway=30,
        options={"require": ["exp", "iat", "aud", "iss", "sub", "email"]},
    )
    if claims["exp"] - claims["iat"] > 660 or claims["iat"] > time.time() + 30:
        raise jwt.InvalidTokenError("Invalid assertion lifetime")
    email = claims["email"]
    if not isinstance(email, str) or "@" not in email:
        raise jwt.InvalidTokenError("Missing user email")
    return email


def get_current_user(request: Request) -> str:
    """Require a verified user; a local identity is allowed only by explicit opt-in."""
    assertion = request.headers.get("X-Goog-IAP-JWT-Assertion")
    if not assertion:
        if UI_CONFIG.ENVIRONMENT == "development" and UI_CONFIG.LOCAL_USER_EMAIL:
            return UI_CONFIG.LOCAL_USER_EMAIL
        raise HTTPException(status_code=401, detail="IAP authentication required")
    try:
        user = verify_assertion(assertion)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid IAP assertion") from None
    except Exception:  # noqa: BLE001 - API/UI boundary must not disclose credentials
        raise HTTPException(
            status_code=503, detail="Identity verification unavailable"
        ) from None
    return user
