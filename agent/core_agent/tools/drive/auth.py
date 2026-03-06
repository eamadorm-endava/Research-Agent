"""Google Drive authentication helpers.

This repo is designed to run in two modes:

1) **Gemini Enterprise (production)**
   - OAuth consent is handled by Gemini Enterprise.
   - Gemini Enterprise injects a short-lived **access token** into the ADK session
     state under the key equal to your `authorizationId`.
   - This module reads that token from `tool_context.state[AUTH_ID]`, where
     `AUTH_ID` is provided via env var `GEMINI_ENTERPRISE_AUTH_ID`.

2) **Local development (optional)**
   - You can enable local OAuth to test the connector outside Gemini Enterprise.
   - This mode is disabled by default and must be explicitly enabled.

Important: In production, do NOT ship client secrets; rely on Gemini Enterprise.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from google.oauth2.credentials import Credentials

# Default scopes for read/search RAG workflows.
# Add drive.file + documents if you enable write-back tools.
DRIVE_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/drive.readonly",
]


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _extract_access_token(maybe_token: Any) -> Optional[str]:
    """Best-effort extraction of an OAuth access token from common shapes."""
    if maybe_token is None:
        return None

    # Most common: a raw token string.
    if isinstance(maybe_token, str) and maybe_token.strip():
        return maybe_token.strip()

    # Sometimes: a dict-like object.
    if isinstance(maybe_token, dict):
        for key in ("access_token", "token", "value"):
            v = maybe_token.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()

    return None


def get_drive_credentials(
    *,
    tool_context: Any | None,
    scopes: list[str] | None = None,
) -> Credentials:
    """Return Google credentials for Drive API calls.

    Resolution order:
    1) Gemini Enterprise injected token via ToolContext state.
    2) ADC (Application Default Credentials) if USE_ADC_FOR_DRIVE=true.
    3) Local OAuth (InstalledAppFlow) if ALLOW_LOCAL_OAUTH=true.

    Args:
        tool_context: ADK ToolContext (passed automatically to tool functions).
        scopes: OAuth scopes.

    Returns:
        google.oauth2.credentials.Credentials

    Raises:
        RuntimeError if no credential source is available.
    """

    scopes = scopes or DRIVE_SCOPES

    # --- 1) Gemini Enterprise token injection ---
    auth_id = os.getenv("GEMINI_ENTERPRISE_AUTH_ID")
    if auth_id and tool_context is not None:
        try:
            injected = getattr(tool_context, "state", {}).get(auth_id)
        except Exception:
            injected = None

        token = _extract_access_token(injected)
        if token:
            return Credentials(token=token, scopes=scopes)

    # --- 2) ADC fallback (service account / user ADC) ---
    if _truthy(os.getenv("USE_ADC_FOR_DRIVE")):
        import google.auth

        creds, _ = google.auth.default(scopes=scopes)
        # google.auth.default returns various credential types; normalize if possible.
        if isinstance(creds, Credentials):
            return creds
        # Some creds types (e.g., google.auth.credentials.Credentials) still work with discovery build.
        return creds  # type: ignore[return-value]

    # --- 3) Local OAuth fallback (explicitly enabled) ---
    if _truthy(os.getenv("ALLOW_LOCAL_OAUTH")):
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow

        client_secrets_path = Path(
            os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS", "client_secret.json")
        )
        token_cache_path = Path(
            os.getenv("DRIVE_TOKEN_CACHE", str(Path(".cache") / "drive_token.json"))
        )
        token_cache_path.parent.mkdir(parents=True, exist_ok=True)

        creds: Credentials | None = None
        if token_cache_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(token_cache_path), scopes=scopes
                )
            except Exception:
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not client_secrets_path.exists():
                    raise FileNotFoundError(
                        f"OAuth client secrets not found at {client_secrets_path}. "
                        "Download OAuth client JSON from Google Cloud Console (Desktop app for local) "
                        "and set GOOGLE_OAUTH_CLIENT_SECRETS env var."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(client_secrets_path), scopes=scopes
                )
                # In some environments you may need flow.run_console().
                creds = flow.run_local_server(port=0)

            token_cache_path.write_text(creds.to_json(), encoding="utf-8")

        if creds is None:
            raise RuntimeError("Local OAuth flow did not return credentials.")

        return creds

    raise RuntimeError(
        "No Google Drive credentials available. "
        "For Gemini Enterprise, set GEMINI_ENTERPRISE_AUTH_ID and configure the agent authorization. "
        "For local testing, set ALLOW_LOCAL_OAUTH=true and GOOGLE_OAUTH_CLIENT_SECRETS=path/to/client_secret.json, "
        "or set USE_ADC_FOR_DRIVE=true to use Application Default Credentials."
    )
