import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from agent.core_agent.config import (
    AgentConfig,
    BigQueryMCPConfig,
    CalendarMCPConfig,
    DriveMCPConfig,
    GCPConfig,
    GCSMCPConfig,
    GoogleAuthConfig,
)


def test_gcp_config_defaults():
    """Test that GCPConfig initialises with default values if no env vars are set."""
    with patch.dict(os.environ, clear=True):
        config = GCPConfig()
        assert config.PROJECT_ID == "dummy-gcp-project-id"
        assert config.REGION == "dummy-gcp-region"
        assert config.PROD_EXECUTION is True


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


def test_gcp_config_prod_execution_alias():
    """Test that PROD_EXECUTION reads from the IS_DEPLOYED alias."""
    with patch.dict(os.environ, {"IS_DEPLOYED": "false"}, clear=True):
        config = GCPConfig()
        assert config.PROD_EXECUTION is False


def test_mcp_servers_config_defaults_to_localhost_urls():
    """Test that MCP server URLs default to local localhost endpoints."""
    with patch.dict(os.environ, clear=True):
        bq_config = BigQueryMCPConfig()
        drive_config = DriveMCPConfig()
        gcs_config = GCSMCPConfig()
        cal_config = CalendarMCPConfig()

    assert bq_config.URL == "http://localhost:8080"
    assert drive_config.URL == "http://localhost:8081"
    assert gcs_config.URL == "http://localhost:8082"
    assert cal_config.URL == "http://localhost:8083"


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
    }
    with patch.dict(os.environ, mock_env, clear=True):
        bq_config = BigQueryMCPConfig()
        drive_config = DriveMCPConfig()

        assert bq_config.GENERAL_TIMEOUT == 120
        assert drive_config.GENERAL_TIMEOUT == 120

        assert bq_config.ENDPOINT == "/custom-mcp"
        assert drive_config.URL == "http://localhost:9090"

        assert drive_config.OAUTH_SCOPES == {
            "https://www.googleapis.com/auth/drive": "google drive access",
        }
        assert bq_config.OAUTH_SCOPES == {
            "https://www.googleapis.com/auth/bigquery": "google bigquery access",
        }


def test_mcp_servers_config_oauth_scopes_validator_dict_vs_list_behavior():
    """Test that validate_oauth_scopes correctly parses both JSON lists and dicts from env vars."""

    # Testing Dict Parsing directly bypassing the list assumption
    mock_env_dict = {
        "DRIVE_OAUTH_SCOPES": '{"https://custom.scope/drive": "custom drive access"}'
    }
    with patch.dict(os.environ, mock_env_dict, clear=True):
        config = DriveMCPConfig()
        assert config.OAUTH_SCOPES == {
            "https://custom.scope/drive": "custom drive access"
        }

    # Testing List of string values hitting the enum fallback mapping
    mock_env_list = {
        "CALENDAR_OAUTH_SCOPES": '["https://www.googleapis.com/auth/calendar.events.readonly"]'
    }
    with patch.dict(os.environ, mock_env_list, clear=True):
        config_list = CalendarMCPConfig()
        assert config_list.OAUTH_SCOPES == {
            "https://www.googleapis.com/auth/calendar.events.readonly": "google calendar access"
        }


def test_google_auth_config_reading_env_vars():
    """Test that GoogleAuthConfig correctly reads primary environment variables."""
    mock_env = {
        "GOOGLE_OAUTH_CLIENT_ID": "test-client-id",
        "GOOGLE_OAUTH_CLIENT_SECRET": "test-client-secret",
        "GOOGLE_OAUTH_REDIRECT_URI": "http://localhost:8000/dev-ui",
        "GOOGLE_OAUTH_AUTH_URI": "https://accounts.google.com/o/oauth2/v2/auth",
        "GOOGLE_OAUTH_TOKEN_URI": "https://oauth2.googleapis.com/token",
    }
    with patch.dict(os.environ, mock_env, clear=True):
        config = GoogleAuthConfig()

    assert config.GOOGLE_OAUTH_CLIENT_ID == "test-client-id"
    assert config.GOOGLE_OAUTH_CLIENT_SECRET == "test-client-secret"
    assert config.GOOGLE_OAUTH_REDIRECT_URI == "http://localhost:8000/dev-ui"
    assert (
        config.GOOGLE_OAUTH_AUTH_URI == "https://accounts.google.com/o/oauth2/v2/auth"
    )
    assert config.GOOGLE_OAUTH_TOKEN_URI == "https://oauth2.googleapis.com/token"


def test_mcp_config_accepts_legacy_auth_id():
    """Test that service-specific alias (GEMINI_DRIVE_AUTH_ID) maps to GEMINI_GOOGLE_AUTH_ID."""
    mock_env = {
        "GEMINI_DRIVE_AUTH_ID": "legacy-drive-id",
    }
    with patch.dict(os.environ, mock_env, clear=True):
        config = DriveMCPConfig()
    assert config.GEMINI_GOOGLE_AUTH_ID == "legacy-drive-id"
