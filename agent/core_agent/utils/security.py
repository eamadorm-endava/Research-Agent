import logging
import os
from typing import Any
from urllib.parse import urlparse

import google.auth
import google.oauth2.id_token
from google.auth.transport.requests import Request


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def get_id_token(audience: str) -> str | None:
    """
    Generate a valid ID token to call a GCP service such as Cloud Run.

    It first tries the metadata server (when running on GCP) and then falls back to
    local ADC credentials for development.
    """
    request = Request()
    try:
        logging.debug("Retrieving ID token from metadata server for audience %s", audience)
        id_token = google.oauth2.id_token.fetch_id_token(request, audience)
        logging.debug("ID token successfully retrieved from metadata server")
        return id_token
    except Exception as exc:
        logging.debug("Metadata-server ID token retrieval failed: %s", exc)

    try:
        logging.debug("Retrieving ID token from local ADC credentials")
        credentials, _ = google.auth.default()
        credentials.refresh(request)
        id_token = getattr(credentials, "id_token", None)
        if id_token:
            logging.debug("ID token retrieved from local ADC credentials")
            return id_token
        logging.warning("ADC credentials did not yield an ID token")
    except Exception as exc:
        logging.warning("Unable to obtain ID token from local ADC credentials: %s", exc)

    return None


def extract_access_token(maybe_token: Any) -> str | None:
    """Extract a bearer token from common state shapes."""
    if maybe_token is None:
        return None
    if isinstance(maybe_token, str) and maybe_token.strip():
        return maybe_token.strip()
    if isinstance(maybe_token, dict):
        for key in ("access_token", "token", "value"):
            value = maybe_token.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def get_delegated_access_token(call_context: Any | None) -> str | None:
    """Read the Gemini Enterprise delegated user token from ADK context state."""
    auth_id = os.getenv("GEMINI_ENTERPRISE_AUTH_ID")
    if not auth_id or call_context is None:
        return None

    state = getattr(call_context, "state", None)
    if state is None:
        return None

    try:
        injected = state.get(auth_id)
    except Exception:
        return None

    return extract_access_token(injected)


def is_local_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return hostname in {"localhost", "127.0.0.1", "0.0.0.0"}


def build_mcp_headers(
    *,
    audience_url: str,
    call_context: Any | None,
    delegated_token_header: str | None = None,
    force_disable_id_token_auth: bool = False,
) -> dict[str, str]:
    """Build headers for MCP requests.

    - Adds a Cloud Run ID token in `Authorization` unless disabled or the target is local.
    - Adds a delegated user access token in a custom header when available.
    """
    headers: dict[str, str] = {}

    if not force_disable_id_token_auth and not is_local_url(audience_url):
        id_token = get_id_token(audience_url)
        if id_token:
            headers["Authorization"] = f"Bearer {id_token}"

    if delegated_token_header:
        delegated_token = get_delegated_access_token(call_context)
        if delegated_token:
            headers[delegated_token_header] = delegated_token

    return headers


def build_mcp_tool_auth(
    *,
    auth_mode: str,
    header_name: str | None = None,
    token_value: str | None = None,
    oauth_client_id: str | None = None,
    oauth_client_secret: str | None = None,
    oauth_token_url: str | None = None,
    oauth_authorization_url: str | None = None,
    oauth_scopes: str | None = None,
) -> dict[str, Any]:
    """Build optional auth kwargs for ``McpToolset``.

    This is meant for authenticating the *agent to the MCP server itself*.
    Gemini Enterprise delegated user Drive tokens are still forwarded per-request via
    ``header_provider``, because those tokens are dynamic and user-specific.

    Supported modes:
    - ``none``: return no auth kwargs.
    - ``api_key_header``: attach a static header value using ADK's auth plumbing.
    - ``oauth2_client_credentials``: configure ADK to exchange client credentials for a
      bearer token when talking to the MCP server.
    """
    normalized_mode = (auth_mode or "none").strip().lower()
    if normalized_mode in {"", "none"}:
        return {}

    try:
        from fastapi.openapi.models import APIKey, APIKeyIn, OAuth2, OAuthFlowClientCredentials, OAuthFlows
        from google.adk.auth import AuthCredential, AuthCredentialTypes, OAuth2Auth
    except Exception as exc:
        logging.warning(
            "Drive MCP auth was requested, but ADK/FastAPI auth models are unavailable. Falling back without McpToolset auth kwargs: %s",
            exc,
        )
        return {}

    if normalized_mode == "api_key_header":
        if not header_name or not token_value:
            logging.warning(
                "DRIVE_MCP_AUTH_MODE=api_key_header requires DRIVE_MCP_AUTH_HEADER_NAME and DRIVE_MCP_AUTH_TOKEN. Falling back without McpToolset auth kwargs."
            )
            return {}
        auth_scheme = APIKey.model_validate(
            {"type": "apiKey", "name": header_name, "in": APIKeyIn.header.value}
        )
        auth_credential = AuthCredential(
            auth_type=AuthCredentialTypes.API_KEY,
            api_key=token_value,
        )
        return {"auth_scheme": auth_scheme, "auth_credential": auth_credential}

    if normalized_mode == "oauth2_client_credentials":
        if not oauth_client_id or not oauth_client_secret:
            logging.warning(
                "DRIVE_MCP_AUTH_MODE=oauth2_client_credentials requires DRIVE_MCP_OAUTH_CLIENT_ID and DRIVE_MCP_OAUTH_CLIENT_SECRET. Falling back without McpToolset auth kwargs."
            )
            return {}
        scopes = {
            scope: scope
            for scope in [item.strip() for item in (oauth_scopes or "").split(",") if item.strip()]
        }
        auth_scheme = OAuth2(
            flows=OAuthFlows(
                clientCredentials=OAuthFlowClientCredentials(
                    tokenUrl=oauth_token_url or "",
                    scopes=scopes,
                )
            )
        )
        auth_credential = AuthCredential(
            auth_type=AuthCredentialTypes.OAUTH2,
            oauth2=OAuth2Auth(
                client_id=oauth_client_id,
                client_secret=oauth_client_secret,
                auth_uri=oauth_authorization_url or None,
            ),
        )
        return {"auth_scheme": auth_scheme, "auth_credential": auth_credential}

    logging.warning(
        "Unsupported DRIVE_MCP_AUTH_MODE=%s. Supported values are none, api_key_header, oauth2_client_credentials. Falling back without McpToolset auth kwargs.",
        auth_mode,
    )
    return {}
