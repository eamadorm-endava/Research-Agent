"""Provider consent and single-use OAuth callbacks behind IAP."""

import base64
import hashlib
import time
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger
from pydantic import ValidationError

from agent.core_agent.config import (
    ATLASSIAN_AUTH_CONFIG,
    GOOGLE_AUTH_CONFIG,
    MICROSOFT_AUTH_CONFIG,
    BaseOAuthConfig,
)
from agent.core_agent.security.token_store import TokenData, token_store

from ..auth import get_current_user
from ..config import OAUTH_CALLBACK_SCRIPT, UI_CONFIG
from ..limits import limiter, request_limit
from ..oauth_state import consume_state, create_state
from ..schemas import OAuthProviderRequest

router = APIRouter()
PROVIDER_CONFIGS = {
    "google": GOOGLE_AUTH_CONFIG,
    "microsoft": MICROSOFT_AUTH_CONFIG,
    "atlassian": ATLASSIAN_AUTH_CONFIG,
}
PKCE_PROVIDERS = {"google", "microsoft"}


def get_cookie_settings(provider: str) -> dict[str, str]:
    """Select constant cookie metadata; URL input never forms cookie attributes."""
    try:
        return OAuthProviderRequest(provider=provider).cookie_settings
    except ValidationError:
        raise HTTPException(400, "Unknown provider") from None


def get_provider_config(provider: str) -> BaseOAuthConfig:
    """Reject unknown providers and missing client configuration."""
    config = PROVIDER_CONFIGS.get(provider)
    if not config:
        raise HTTPException(400, "Unknown provider")
    if (
        not config.CLIENT_ID
        or not config.CLIENT_SECRET
        or config.CLIENT_ID.startswith("mock-")
        or config.CLIENT_SECRET.startswith("mock-")
    ):
        raise HTTPException(503, "OAuth provider is not configured")
    return config


def redirect_uri(provider: str) -> str:
    """Use the configured public origin, never a caller-provided Host header."""
    callback_path = OAuthProviderRequest(provider=provider).callback_path
    return f"{UI_CONFIG.PUBLIC_BASE_URL.rstrip('/')}{callback_path}"


@router.get("/{provider}/login")
@limiter.limit(request_limit)
def login(provider: str, request: Request, user_id: str = Depends(get_current_user)):
    """Start consent and set a secure cookie binding the popup to its transaction."""
    config = get_provider_config(provider)
    transaction = create_state(user_id, provider)
    state = transaction["state"]
    browser_secret = transaction["browser_secret"]
    verifier = transaction["verifier"]
    params = _authorization_params(provider, config, state, verifier)
    response = RedirectResponse(f"{config.AUTH_URI}?{urlencode(params)}")
    cookie_settings = get_cookie_settings(provider)
    cookie_name, cookie_path = cookie_settings["name"], cookie_settings["path"]
    response.set_cookie(
        cookie_name,
        browser_secret,
        httponly=True,
        secure=UI_CONFIG.ENVIRONMENT != "development",
        samesite="lax",
        max_age=UI_CONFIG.OAUTH_STATE_SECONDS,
        path=cookie_path,
    )
    return response


def _authorization_params(
    provider: str, config: BaseOAuthConfig, state: str, verifier: str
) -> dict[str, str]:
    """Build provider authorization parameters from trusted configuration."""
    params = {
        "client_id": config.CLIENT_ID,
        "redirect_uri": redirect_uri(provider),
        "response_type": "code",
        "scope": " ".join(config.SCOPES),
        "state": state,
    }
    if provider in PKCE_PROVIDERS:
        params["code_challenge"] = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        params["code_challenge_method"] = "S256"
    if provider == "google":
        params.update(access_type="offline", prompt="consent")
    elif provider == "microsoft":
        params["prompt"] = "select_account"
    else:
        # Atlassian's documented confidential 3LO flow uses a client secret.
        params.update(audience="api.atlassian.com", prompt="consent")
    return params


@router.get("/{provider}/callback")
@limiter.limit(request_limit)
def callback(
    provider: str,
    request: Request,
    state: str,
    code: str | None = None,
    error: str | None = None,
    user_id: str = Depends(get_current_user),
):
    """Validate the transaction before exchanging or storing any credentials."""
    config = get_provider_config(provider)
    cookie_settings = get_cookie_settings(provider)
    cookie_name, cookie_path = cookie_settings["name"], cookie_settings["path"]
    verifier = consume_state(
        state,
        request.cookies.get(cookie_name, ""),
        user_id,
        provider,
    )
    if error or not code:
        raise HTTPException(400, "Provider authorization was not completed")
    payload = {
        "client_id": config.CLIENT_ID,
        "client_secret": config.CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri(provider),
    }
    if provider in PKCE_PROVIDERS:
        payload["code_verifier"] = verifier
    tokens = exchange_tokens(provider, config.TOKEN_URI, payload)
    token_store.save_tokens(user_id=user_id, provider=provider, token_data=tokens)
    response = HTMLResponse(
        "<html><head><title>Authorization completed</title>"
        f"<script>{OAUTH_CALLBACK_SCRIPT}</script>"
        "</head>"
        "<body><p>Account connected. Close this tab and continue in OSIRIS.</p>"
        "</body></html>"
    )
    response.delete_cookie(cookie_name, path=cookie_path)
    response.headers["Cache-Control"] = "no-store"
    return response


def exchange_tokens(
    provider: str, token_uri: str, payload: dict[str, str]
) -> TokenData:
    """Exchange a code with a timeout, keeping credentials and responses out of logs."""
    try:
        body = {"json": payload} if provider == "atlassian" else {"data": payload}
        response = requests.post(
            token_uri,
            timeout=UI_CONFIG.HTTP_TIMEOUT_SECONDS,
            **body,
        )
        response.raise_for_status()
        tokens = response.json()
        return TokenData(
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            expires_at=time.time() + float(tokens["expires_in"]),
        )
    except (requests.RequestException, KeyError, ValueError):
        logger.warning("OAuth token exchange failed for {}", provider)
        raise HTTPException(502, "Provider token exchange failed") from None
