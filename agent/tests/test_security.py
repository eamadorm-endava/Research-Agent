from unittest.mock import patch, MagicMock

from agent.core_agent.utils.security import get_id_token


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
