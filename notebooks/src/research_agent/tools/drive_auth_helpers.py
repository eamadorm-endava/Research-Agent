    """Authentication helpers for Google Drive.

- Local dev: OAuth installed app flow (token cached on disk)
- Production (Gemini Enterprise): access token injected into ADK session state

Keep production tokens out of disk; rely on ToolContext state.
"""

from __future__ import annotations
from typing import Optional
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

def creds_from_local_oauth(client_secrets_path: Path, token_cache_path: Path, scopes) -> Credentials:
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if token_cache_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_cache_path), scopes=scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not client_secrets_path.exists():
                raise FileNotFoundError(
                    f"OAuth client secrets not found at {client_secrets_path}. "
                    "Download it from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_path), scopes=scopes)
            creds = flow.run_local_server(port=0)

        token_cache_path.parent.mkdir(parents=True, exist_ok=True)
        token_cache_path.write_text(creds.to_json(), encoding="utf-8")

    return creds

def creds_from_access_token(access_token: str, scopes) -> Credentials:
    return Credentials(token=access_token, scopes=scopes)
