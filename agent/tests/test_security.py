import base64
import json
from unittest.mock import patch, MagicMock

from agent.core_agent.security import (
    extract_user_email_from_token,
    get_id_token,
    get_ge_oauth_token,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_jwt_token(payload: dict) -> str:
    """Build a minimal JWT-formatted string with the given payload for testing."""
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
    encoded = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    )
    return f"{header}.{encoded}.fakesignature"


# ─── extract_user_email_from_token ────────────────────────────────────────────


def test_extract_user_email_from_token_returns_email_from_valid_jwt():
    """Should return the email claim when the token is a valid JWT containing one."""
    token = _make_jwt_token({"email": "ge_user@company.com", "sub": "12345"})
    assert extract_user_email_from_token(token) == "ge_user@company.com"


def test_extract_user_email_from_token_returns_none_when_no_email_claim():
    """Should return None when the JWT payload is valid but contains no email claim."""
    token = _make_jwt_token({"sub": "12345", "name": "Test User"})
    assert extract_user_email_from_token(token) is None


def test_extract_user_email_from_token_returns_none_for_opaque_token():
    """Should return None when the token is not in JWT format (lacks three dot-separated segments)."""
    assert extract_user_email_from_token("opaque-access-token-12345") is None


def test_extract_user_email_from_token_returns_none_for_invalid_base64_payload():
    """Should return None gracefully when the JWT middle segment cannot be base64-decoded."""
    assert extract_user_email_from_token("header.!!invalid!!.signature") is None


@patch("google.oauth2.id_token.fetch_id_token")
def test_get_id_token_server_success(mock_fetch_id_token):
    """Test successful ID token retrieval from the server metadata."""
    mock_fetch_id_token.return_value = "mock_server_id_token_123"

    token = get_id_token("https://fake-audience.run.app")

    assert token == "mock_server_id_token_123"
    mock_fetch_id_token.assert_called_once()


@patch("google.oauth2.id_token.fetch_id_token")
@patch("google.auth.default")
def test_get_id_token_fallback_local(mock_auth_default, mock_fetch_id_token):
    """Test that it correctly falls back to local credentials if server fetch fails."""
    # Force server fetch to fail
    mock_fetch_id_token.side_effect = Exception("Metadata server not found")

    # Mock local user credentials setup
    mock_credentials = MagicMock()
    mock_credentials.id_token = "mock_personal_token_456"
    mock_auth_default.return_value = (mock_credentials, "test-project")

    token = get_id_token("https://fake-audience.run.app")

    assert token == "mock_personal_token_456"
    mock_credentials.refresh.assert_called_once()


@patch("google.oauth2.id_token.fetch_id_token")
@patch("google.auth.default")
def test_get_id_token_complete_failure(mock_auth_default, mock_fetch_id_token):
    """Test the edge case where no token can be generated anywhere."""
    mock_fetch_id_token.side_effect = Exception("Metadata server not found")

    mock_credentials = MagicMock()
    mock_credentials.id_token = None  # User hasn't logged in locally
    mock_auth_default.return_value = (mock_credentials, "test-project")

    token = get_id_token("https://fake-audience.run.app")

    assert token is None


@patch("google.oauth2.id_token.fetch_id_token")
@patch("google.auth.default")
def test_get_id_token_adc_raises_exception(mock_auth_default, mock_fetch_id_token):
    """Test that get_id_token returns None when ADC itself throws an exception."""
    mock_fetch_id_token.side_effect = Exception("Metadata server not found")
    mock_auth_default.side_effect = Exception("No credentials configured")

    token = get_id_token("https://fake-audience.run.app")

    assert token is None


def test_get_ge_oauth_token_success():
    """Test that get_ge_oauth_token returns the token when present in context state."""
    ctx = MagicMock()
    ctx.state = {"auth-resource-id": "delegated-token-value"}

    token = get_ge_oauth_token(ctx, "auth-resource-id")

    assert token == "delegated-token-value"


def test_get_ge_oauth_token_missing_key():
    """Test that get_ge_oauth_token returns None when the auth_id is not in state."""
    ctx = MagicMock()
    ctx.state = {}

    token = get_ge_oauth_token(ctx, "nonexistent-auth-id")

    assert token is None
