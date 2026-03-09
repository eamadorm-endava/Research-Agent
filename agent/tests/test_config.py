import pytest
import os
from unittest.mock import patch
from pydantic import ValidationError

from agent.core_agent.config import GCPConfig, AgentConfig, MCPServersConfig


def test_gcp_config_defaults():
    """Test that GCPConfig initialises with default values if no env vars are set."""
    # Ensure no conflicting env vars in this isolated test
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
        # Default fallback
        assert config.TEMPERATURE == 0.5

    # Test invalid temperature (> 1.0)
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
    }
    with patch.dict(os.environ, mock_env, clear=True):
        config = MCPServersConfig()
        assert config.GENERAL_TIMEOUT == 120
        assert config.BIGQUERY_ENDPOINT == "/custom-mcp"
