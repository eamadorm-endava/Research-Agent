"""Render one connection card and confirm consent using the authenticated API."""

import json
import urllib.request

import requests
import streamlit as st

PROVIDER_LABELS = {
    "google": "Google Workspace",
    "microsoft": "Microsoft 365",
    "atlassian": "Atlassian",
}


def request_headers(api_url: str) -> dict[str, str]:
    """Forward the user's signed assertion separately from the service identity."""
    headers = {
        "X-Osiris-IAP-Assertion": st.context.headers.get("X-Goog-IAP-JWT-Assertion", "")
    }
    audience = api_url.replace("/api", "")
    try:
        request = urllib.request.Request(
            "http://metadata.google.internal/computeMetadata/v1/instance/"
            f"service-accounts/default/identity?audience={audience}",
            headers={"Metadata-Flavor": "Google"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            headers["Authorization"] = f"Bearer {response.read().decode('utf-8')}"
    except (OSError, ValueError):
        pass  # Local development has no metadata server; the API still verifies IAP.
    return headers


def connection_card(provider: str, public_base_url: str) -> str:
    """Build fixed provider metadata and a user-initiated, reusable OAuth popup."""
    label = PROVIDER_LABELS[provider]
    login_url = json.dumps(
        f"{public_base_url}/api/auth/{provider}/login?connect_all=true"
    )
    return f"""<style>
  body {{ margin: 0; color: #e6e7eb; font-family: sans-serif; }}
  button {{ display: flex; align-items: center; gap: 12px; width: 100%;
    max-width: 560px; padding: 18px 20px; background: #15191f;
    color: inherit; border: 1px solid #303640; border-radius: 12px;
    cursor: pointer; text-align: left; font: inherit; font-size: 14px; }}
  button:hover {{ background: #1c222b; border-color: #606a7a; }}
  button:focus-visible {{ outline: 2px solid #a4b4cb; outline-offset: 2px; }}
  .badge {{ display: grid; place-items: center; width: 30px; height: 30px;
    flex-shrink: 0; border: 1px solid #444b58; border-radius: 8px; }}
  .muted {{ color: #a4aab5; }} .arrow {{ margin-left: auto; color: #a4aab5; }}
  #blocked {{ font-size: 12px; color: #a4aab5; margin-top: 8px; }}
</style>
<button onclick="connect()">
  <span class="badge" aria-hidden="true">{label[0]}</span>
  <span><span class="muted">Authentication Required:</span> {label} Connection</span>
  <span class="arrow" aria-hidden="true">↗</span>
</button>
<div id="blocked" role="status"></div>
<script>
  function connect() {{
    const popup = window.open({login_url}, 'OSIRISConnections',
      'popup=yes,width=520,height=720,resizable=yes,scrollbars=yes');
    if (popup) popup.focus();
    else document.getElementById('blocked').textContent = 'Allow pop-ups to connect.';
  }}
</script>
"""


@st.fragment(run_every="3s")
def render_authentication(api_url: str, public_base_url: str) -> None:
    """Advance on server-confirmed connections and resume the original chat once ready."""
    try:
        response = requests.get(
            f"{api_url}/auth/status", headers=request_headers(api_url), timeout=10
        )
        response.raise_for_status()
        missing = response.json()["missing_providers"]
        if missing != st.session_state.required_connections:
            st.session_state.required_connections = missing
            st.rerun()
    except requests.RequestException as error:
        if error.response is not None and error.response.status_code == 401:
            st.error("Your access session expired. Reload this page and try again.")
            return
        st.caption("Checking connection…")
    if st.session_state.required_connections:
        provider = st.session_state.required_connections[0]
        st.iframe(connection_card(provider, public_base_url), height=100)
