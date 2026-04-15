import os
from unittest.mock import patch, MagicMock

from agent.core_agent.config import BigQueryMCPConfig, GCSMCPConfig, GoogleAuthConfig
from agent.core_agent.builder.mcp_factory import MCPToolsetBuilder


import pytest


# Suppress ADK internal deprecation warnings
pytestmark = pytest.mark.filterwarnings(
    "ignore:This method is deprecated. Use credential_key instead.:DeprecationWarning"
)


def test_get_mcp_toolset_local_with_scopes():
    """Test factory creates a tool with correct local Auth Scheme structures."""
    with patch.dict(os.environ, clear=True):
        mcp_config = BigQueryMCPConfig()
        auth_config = GoogleAuthConfig()

    builder = MCPToolsetBuilder(auth_config)
    tool = builder.build(mcp_config, prod_execution=False)

    assert tool._connection_params.url == "http://localhost:8080/mcp"

    # Check that it uses local Auth Scheme since it has scopes
    assert tool._auth_scheme is not None
    assert tool._auth_credential is not None


def test_get_mcp_toolset_local_with_gcs_scopes():
    """Test factory creates a GCS tool with delegated OAuth locally."""
    with patch.dict(os.environ, clear=True):
        mcp_config = GCSMCPConfig()
        auth_config = GoogleAuthConfig()

    builder = MCPToolsetBuilder(auth_config)
    tool = builder.build(mcp_config, prod_execution=False)

    assert tool._connection_params.url == "http://localhost:8082/mcp"

    assert getattr(tool, "_auth_scheme", None) is not None
    assert getattr(tool, "_auth_credential", None) is not None


def test_get_mcp_toolset_prod_mode_logic():
    """Test factory prod mode structures (delegated token, no ADK schemes)."""
    with patch.dict(os.environ, {"BIGQUERY_AUTH_ID": "test-id"}, clear=True):
        mcp_config = BigQueryMCPConfig()
        auth_config = GoogleAuthConfig()

    builder = MCPToolsetBuilder(auth_config)
    tool = builder.build(mcp_config, prod_execution=True)

    # NO explicit auth scheme inside the ADK in prod
    assert getattr(tool, "_auth_scheme", None) is None
    assert getattr(tool, "_auth_credential", None) is None

    # Check header provider logic
    ctx = MagicMock()
    ctx.state = {"test-id": "delegated-token"}

    with patch(
        "agent.core_agent.builder.mcp_factory.get_id_token", return_value="id-token"
    ):
        headers = tool._header_provider(ctx)
        assert headers["X-Serverless-Authorization"] == "Bearer id-token"
        assert headers["Authorization"] == "Bearer delegated-token"


def test_get_mcp_toolset_prod_mode_gcs_uses_delegated_token():
    """Test factory prod mode for GCS forwards the delegated OAuth token."""
    with patch.dict(os.environ, {"GCS_AUTH_ID": "gcs-auth-id"}, clear=True):
        mcp_config = GCSMCPConfig()
        auth_config = GoogleAuthConfig()

    builder = MCPToolsetBuilder(auth_config)
    tool = builder.build(mcp_config, prod_execution=True)

    # No ADK schemes
    assert getattr(tool, "_auth_scheme", None) is None

    # Check header provider logic (Authorization must be present)
    ctx = MagicMock()
    ctx.state = {"gcs-auth-id": "delegated-token"}
    with patch(
        "agent.core_agent.builder.mcp_factory.get_id_token", return_value="id-token"
    ):
        headers = tool._header_provider(ctx)
        assert headers["X-Serverless-Authorization"] == "Bearer id-token"
        assert headers["Authorization"] == "Bearer delegated-token"


def test_mcp_config_alias_precedence():
    """Test that specific service alias takes precedence over generic."""
    with patch.dict(
        os.environ,
        {"BIGQUERY_AUTH_ID": "specific-id", "GEMINI_GOOGLE_AUTH_ID": "generic-id"},
        clear=True,
    ):
        mcp_config = BigQueryMCPConfig()

    assert mcp_config.GEMINI_GOOGLE_AUTH_ID == "specific-id"
