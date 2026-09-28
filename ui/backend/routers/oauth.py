import time
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from loguru import logger
import requests
import urllib.parse

# We import the configurations from the core_agent
from agent.core_agent.config import (
    GOOGLE_AUTH_CONFIG,
    MICROSOFT_AUTH_CONFIG,
    ATLASSIAN_AUTH_CONFIG,
)
from agent.core_agent.security.token_store import token_store, TokenData

router = APIRouter()


# Helper function to extract user_id from IAP headers
def get_current_user(request: Request) -> str:
    # In production with IAP, the email is in this header:
    user_email = request.headers.get("X-Goog-Authenticated-User-Email")
    if not user_email:
        # For local development fallback
        logger.warning("No IAP header found. Using mock-user for development.")
        return "mock-user@example.com"

    # IAP returns emails with 'accounts.google.com:' prefix sometimes
    if user_email.startswith("accounts.google.com:"):
        user_email = user_email.replace("accounts.google.com:", "")

    return user_email


PROVIDER_CONFIGS = {
    "google": GOOGLE_AUTH_CONFIG,
    "microsoft": MICROSOFT_AUTH_CONFIG,
    "atlassian": ATLASSIAN_AUTH_CONFIG,
}


def get_provider_config(provider: str):
    config = PROVIDER_CONFIGS.get(provider)
    if not config:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    return config


@router.get("/{provider}/login")
async def login(provider: str, request: Request):
    """
    Redirects the user to the provider's OAuth 2.0 authorization screen.
    """
    config = get_provider_config(provider)

    # We pass the redirect URI configured in the environment
    redirect_uri = config.REDIRECT_URI

    # Scopes might be a list or a dict, we join them with spaces
    scopes = config.OAUTH_SCOPES
    if isinstance(scopes, dict):
        scope_str = " ".join(scopes.keys())
    else:
        scope_str = " ".join(scopes)

    params = {
        "client_id": config.CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope_str,
        "access_type": "offline",  # Needed for Google to return a refresh token
        "prompt": "consent",  # Force consent to ensure refresh token
    }

    # Atlassian requires an audience parameter
    if provider == "atlassian":
        params["audience"] = "api.atlassian.com"

    auth_url = f"{config.AUTH_URI}?{urllib.parse.urlencode(params)}"
    logger.info(f"Redirecting user to {provider} login...")
    return RedirectResponse(url=auth_url)


@router.get("/{provider}/callback")
async def callback(
    provider: str, request: Request, code: str, user_id: str = Depends(get_current_user)
):
    """
    Handles the OAuth 2.0 callback, exchanges the code for tokens,
    and saves them in Firestore.
    """
    logger.info(f"Received OAuth callback for {provider} from user {user_id}")
    config = get_provider_config(provider)

    payload = {
        "client_id": config.CLIENT_ID,
        "client_secret": config.CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": config.REDIRECT_URI,
    }

    try:
        # Atlassian expects JSON, others expect Form URL-Encoded
        if provider == "atlassian":
            response = requests.post(config.TOKEN_URI, json=payload)
        else:
            response = requests.post(config.TOKEN_URI, data=payload)

        response.raise_for_status()
        data = response.json()

        # Build token data
        token_data = TokenData(
            access_token=data["access_token"],
            refresh_token=data.get(
                "refresh_token"
            ),  # Important: user must consent to get this
            expires_at=time.time() + float(data["expires_in"]),
        )

        # Save securely to Firestore
        token_store.save_tokens(
            user_id=user_id, provider=provider, token_data=token_data
        )
        logger.info(f"Successfully saved {provider} tokens for {user_id}")

        # Redirect back to the chat UI
        return RedirectResponse(url="/")

    except Exception as e:
        logger.error(f"Failed to exchange code for {provider} tokens: {e}")
        if isinstance(e, requests.exceptions.HTTPError):
            logger.error(f"Response: {e.response.text}")
        raise HTTPException(
            status_code=500, detail=f"Authentication failed for {provider}"
        )
