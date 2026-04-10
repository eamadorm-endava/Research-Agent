import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from agent.core_agent.config import AgentConfig, GCPConfig, MCPServersConfig


def test_gcp_config_defaults():
    """Test that GCPConfig initialises with default values if no env vars are set."""
    with patch.dict(os.environ, clear=True):
        config = GCPConfig()
        assert config.PROJECT_ID == "dummy-gcp-project-id"
        assert config.REGION == "dummy-gcp-region"


def test_gcp_config_override():
    """Test that GCPConfig correctly reads from environment variables."""
    mock_env = {
        "PROJECT_ID": "test-project-123",
        "REGION": "europe-west1",
    }
    with patch.dict(os.environ, mock_env, clear=True):
        config = GCPConfig()
        assert config.PROJECT_ID == "test-project-123"
        assert config.REGION == "europe-west1"


def test_mcp_servers_config_defaults_to_localhost_urls():
    """Test that MCP server URLs default to local localhost endpoints."""
    with patch.dict(os.environ, clear=True):
        config = MCPServersConfig()

    assert config.BIGQUERY_URL == "http://localhost:8080"
    assert config.DRIVE_URL == "http://localhost:8081"
    assert config.GCS_URL == "http://localhost:8082"
    assert config.CALENDAR_URL == "http://localhost:8083"


def test_agent_config_validation():
    """Test that AgentConfig enforces data types and constraints."""
    with patch.dict(os.environ, clear=True):
        config = AgentConfig()
        assert config.TEMPERATURE == 0.3

    mock_env_invalid = {"TEMPERATURE": "1.5"}
    with patch.dict(os.environ, mock_env_invalid, clear=True):
        with pytest.raises(ValidationError) as exc_info:
            AgentConfig()
        assert "Input should be less than or equal to 1" in str(exc_info.value)

    mock_env_invalid_low = {"TEMPERATURE": "-0.5"}
    with patch.dict(os.environ, mock_env_invalid_low, clear=True):
        with pytest.raises(ValidationError) as exc_info:
            AgentConfig()
        assert "Input should be greater than or equal to 0" in str(exc_info.value)


def test_mcp_servers_config():
    """Test that MCP server config correctly assigns custom timeout values."""
    mock_env = {
        "GENERAL_TIMEOUT": "120",
        "BIGQUERY_ENDPOINT": "/custom-mcp",
        "DRIVE_URL": "http://localhost:9090",
        "DRIVE_OAUTH_SCOPES": '["https://www.googleapis.com/auth/drive"]',
        "BIGQUERY_OAUTH_SCOPES": '["https://www.googleapis.com/auth/bigquery"]',
        "GOOGLE_OAUTH_CLIENT_ID": "shared-google-client-id",
        "GEMINI_GOOGLE_AUTH_ID": "shared-google-auth-id",
    }
    with patch.dict(os.environ, mock_env, clear=True):
        config = MCPServersConfig()
        assert config.GENERAL_TIMEOUT == 120
        assert config.BIGQUERY_ENDPOINT == "/custom-mcp"
        assert config.DRIVE_URL == "http://localhost:9090"
        assert config.GOOGLE_OAUTH_CLIENT_ID == "shared-google-client-id"
        assert config.GEMINI_GOOGLE_AUTH_ID == "shared-google-auth-id"
        assert config.DRIVE_OAUTH_SCOPES == {
            "https://www.googleapis.com/auth/drive": "google drive access",
        }
        assert config.BIGQUERY_OAUTH_SCOPES == {
            "https://www.googleapis.com/auth/bigquery": "google bigquery access",
        }


def test_mcp_servers_config_oauth_scopes_validator_dict_vs_list_behavior():
    """Test that validate_oauth_scopes correctly parses both JSON lists and dicts from env vars."""

    # Testing Dict Parsing directly bypassing the list assumption
    mock_env_dict = {
        "DRIVE_OAUTH_SCOPES": '{"https://custom.scope/drive": "custom drive access"}'
    }
    with patch.dict(os.environ, mock_env_dict, clear=True):
        config = MCPServersConfig()
        assert config.DRIVE_OAUTH_SCOPES == {
            "https://custom.scope/drive": "custom drive access"
        }

    # Testing List of string values hitting the enum fallback mapping
    mock_env_list = {
        "CALENDAR_OAUTH_SCOPES": '["https://www.googleapis.com/auth/calendar.events.readonly"]'
    }
    with patch.dict(os.environ, mock_env_list, clear=True):
        config_list = MCPServersConfig()
        assert config_list.CALENDAR_OAUTH_SCOPES == {
            "https://www.googleapis.com/auth/calendar.events.readonly": "google calendar access"
        }


def test_mcp_servers_config_accepts_legacy_google_auth_env_names():
    mock_env = {
        "DRIVE_OAUTH_CLIENT_ID": "legacy-client-id",
        "DRIVE_OAUTH_CLIENT_SECRET": "legacy-client-secret",
        "DRIVE_OAUTH_REDIRECT_URI": "http://localhost:8000/dev-ui",
        "DRIVE_OAUTH_AUTH_URI": "https://accounts.google.com/o/oauth2/v2/auth",
        "DRIVE_OAUTH_TOKEN_URI": "https://oauth2.googleapis.com/token",
        "GEMINI_DRIVE_AUTH_ID": "legacy-auth-id",
    }
    with patch.dict(os.environ, mock_env, clear=True):
        config = MCPServersConfig()

    assert config.GOOGLE_OAUTH_CLIENT_ID == "legacy-client-id"
    assert config.GOOGLE_OAUTH_CLIENT_SECRET == "legacy-client-secret"
    assert config.GOOGLE_OAUTH_REDIRECT_URI == "http://localhost:8000/dev-ui"
    assert (
        config.GOOGLE_OAUTH_AUTH_URI == "https://accounts.google.com/o/oauth2/v2/auth"
    )
    assert config.GOOGLE_OAUTH_TOKEN_URI == "https://oauth2.googleapis.com/token"
    assert config.GEMINI_GOOGLE_AUTH_ID == "legacy-auth-id"
