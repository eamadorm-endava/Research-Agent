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


def test_mcp_servers_config():
    """Test that MCP server config correctly assigns custom timeout values."""
    mock_env = {
        "GENERAL_TIMEOUT": "120",
        "BIGQUERY_ENDPOINT": "/custom-mcp",
        "DRIVE_URL": "http://localhost:9090",
        "DRIVE_OAUTH_SCOPES": '["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/drive.file"]',
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
            "https://www.googleapis.com/auth/drive.readonly": "google drive access",
            "https://www.googleapis.com/auth/drive.file": "google drive access",
        }
        assert config.BIGQUERY_OAUTH_SCOPES == {
            "https://www.googleapis.com/auth/bigquery": "google bigquery access",
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
