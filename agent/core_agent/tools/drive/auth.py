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

import os
from pathlib import Path
from typing import Any

from google.oauth2.credentials import Credentials

from .config import DRIVE_AUTH_ENV_CONFIG, DRIVE_SCOPE_CONFIG


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _extract_access_token(maybe_token: Any) -> str | None:
    """Best-effort extraction of an OAuth access token from common shapes."""
    if maybe_token is None:
        return None

    if isinstance(maybe_token, str) and maybe_token.strip():
        return maybe_token.strip()

    if isinstance(maybe_token, dict):
        for key in DRIVE_AUTH_ENV_CONFIG.injected_token_candidate_keys:
            value = maybe_token.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

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
    """

    scopes = scopes or DRIVE_SCOPE_CONFIG.read_only_list()

    auth_id = os.getenv(DRIVE_AUTH_ENV_CONFIG.gemini_enterprise_auth_id_env)
    if auth_id and tool_context is not None:
        try:
            injected = getattr(tool_context, "state", {}).get(auth_id)
        except Exception:
            injected = None

        token = _extract_access_token(injected)
        if token:
            return Credentials(token=token, scopes=scopes)

    if _truthy(os.getenv(DRIVE_AUTH_ENV_CONFIG.use_adc_env)):
        import google.auth

        creds, _ = google.auth.default(scopes=scopes)
        if isinstance(creds, Credentials):
            return creds
        return creds  # type: ignore[return-value]

    if _truthy(os.getenv(DRIVE_AUTH_ENV_CONFIG.allow_local_oauth_env)):
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow

        client_secrets_path = Path(
            os.getenv(
                DRIVE_AUTH_ENV_CONFIG.oauth_client_secrets_env,
                DRIVE_AUTH_ENV_CONFIG.default_client_secrets_path,
            )
        )
        token_cache_path = Path(
            os.getenv(
                DRIVE_AUTH_ENV_CONFIG.token_cache_env,
                DRIVE_AUTH_ENV_CONFIG.default_token_cache_path,
            )
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
                        f"and set {DRIVE_AUTH_ENV_CONFIG.oauth_client_secrets_env} env var."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(client_secrets_path), scopes=scopes
                )
                creds = flow.run_local_server(port=0)

            token_cache_path.write_text(creds.to_json(), encoding="utf-8")

        if creds is None:
            raise RuntimeError("Local OAuth flow did not return credentials.")

        return creds

    raise RuntimeError(
        "No Google Drive credentials available. "
        f"For Gemini Enterprise, set {DRIVE_AUTH_ENV_CONFIG.gemini_enterprise_auth_id_env} and configure the agent authorization. "
        f"For local testing, set {DRIVE_AUTH_ENV_CONFIG.allow_local_oauth_env}=true and "
        f"{DRIVE_AUTH_ENV_CONFIG.oauth_client_secrets_env}=path/to/client_secret.json, "
        f"or set {DRIVE_AUTH_ENV_CONFIG.use_adc_env}=true to use Application Default Credentials."
    )
