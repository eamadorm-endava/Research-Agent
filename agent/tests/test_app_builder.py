import pytest
from unittest.mock import MagicMock
from agent.core_agent.builder import AppBuilder
from agent.core_agent.config import GCPConfig, AgentConfig
from agent.core_agent.plugins import DeduplicatingArtifactPlugin
from google.adk.agents import BaseAgent
from google.adk.plugins.base_plugin import BasePlugin
from vertexai.agent_engines import AdkApp
from google.adk.apps.app import App


class _StubPlugin(BasePlugin):
    """Minimal concrete BasePlugin for testing plugin registration."""

    def __init__(self) -> None:
        super().__init__(name="stub_plugin")


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
        "agent": AgentConfig(AGENT_NAME="test_agent"),
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
    assert app.name == "test_agent"


def test_app_builder_default_plugin_is_deduplicating(mock_agent, mock_configs):
    """Test that AppBuilder registers DeduplicatingArtifactPlugin by default."""
    builder = AppBuilder(
        agent=mock_agent,
        gcp_config=mock_configs["gcp_local"],
        agent_config=mock_configs["agent"],
    )

    app = builder.build()

    assert any(isinstance(p, DeduplicatingArtifactPlugin) for p in app.plugins)


def test_app_builder_with_plugins(mock_agent, mock_configs):
    """Test that AppBuilder correctly appends plugins."""
    builder = AppBuilder(
        agent=mock_agent,
        gcp_config=mock_configs["gcp_local"],
        agent_config=mock_configs["agent"],
    )

    stub_plugin = _StubPlugin()
    builder.with_plugins([stub_plugin])

    app = builder.build()
    assert stub_plugin in app.plugins
