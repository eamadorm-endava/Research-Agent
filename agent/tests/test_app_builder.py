import pytest
from unittest.mock import MagicMock
from agent.core_agent.builder import AppBuilder
from agent.core_agent.config import GCPConfig, AgentConfig
from google.adk.agents import BaseAgent
from vertexai.agent_engines import AdkApp
from google.adk.apps.app import App


@pytest.fixture
def mock_agent():
    return MagicMock(spec=BaseAgent)


@pytest.fixture
def mock_configs():
    return {
        "gcp_prod": GCPConfig(
            PROD_EXECUTION=True, ARTIFACT_BUCKET="test-bucket", REGION="us-central1"
        ),
        "gcp_local": GCPConfig(PROD_EXECUTION=False),
        "agent": AgentConfig(AGENT_NAME="test-agent", ENABLE_TRACING=True),
    }


def test_app_builder_prod_assembly(mock_agent, mock_configs):
    """Test that AppBuilder creates an AdkApp when PROD_EXECUTION is True."""
    builder = AppBuilder(
        agent=mock_agent,
        gcp_config=mock_configs["gcp_prod"],
        agent_config=mock_configs["agent"],
    )

    app = builder.build()

    assert isinstance(app, AdkApp)
    # Check that it was initialized with correct bucket and name
    # AdkApp attributes might be internal, but we can verify it's the right class


def test_app_builder_local_assembly(mock_agent, mock_configs):
    """Test that AppBuilder creates a standard App when PROD_EXECUTION is False."""
    builder = AppBuilder(
        agent=mock_agent,
        gcp_config=mock_configs["gcp_local"],
        agent_config=mock_configs["agent"],
    )

    app = builder.build()

    assert isinstance(app, App)
    assert app.name == "test-agent"


def test_app_builder_with_plugins(mock_agent, mock_configs):
    """Test that AppBuilder correctly appends plugins."""
    builder = AppBuilder(
        agent=mock_agent,
        gcp_config=mock_configs["gcp_local"],
        agent_config=mock_configs["agent"],
    )

    mock_plugin = MagicMock()
    builder.with_plugins([mock_plugin])

    app = builder.build()
    assert mock_plugin in app.plugins
