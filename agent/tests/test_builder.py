import pytest
from unittest.mock import patch, MagicMock
from agent.core_agent.builder import AgentBuilder
from agent.core_agent.config import (
    AgentConfig,
    GCPConfig,
    GoogleAuthConfig,
    BigQueryMCPConfig,
)


@pytest.fixture
def mock_configs():
    return {
        "agent": AgentConfig(),
        "gcp": GCPConfig(PROJECT_ID="test-project", REGION="us-central1"),
        "auth": GoogleAuthConfig(),
    }


@patch("agent.core_agent.builder.agent_builder.vertexai.Client")
def test_agent_builder_initialization(mock_vertex_client, mock_configs):
    """Test that AgentBuilder initializes VertexAI client on startup."""
    builder = AgentBuilder(
        agent_config=mock_configs["agent"],
        gcp_config=mock_configs["gcp"],
        auth_config=mock_configs["auth"],
    )

    mock_vertex_client.assert_called_once_with(
        project="test-project", location="us-central1"
    )
    assert builder._tools == []


@patch("agent.core_agent.builder.agent_builder.vertexai.Client")
def test_agent_builder_fluent_chaining(mock_vertex_client, mock_configs):
    """Test that builder methods support fluent chaining and append tools."""
    builder = AgentBuilder(
        agent_config=mock_configs["agent"],
        gcp_config=mock_configs["gcp"],
        auth_config=mock_configs["auth"],
    )

    with (
        patch(
            "agent.core_agent.builder.agent_builder.get_skill_toolset"
        ) as mock_skills,
        patch.object(builder._mcp_builder, "build") as mock_mcp_build,
    ):
        mock_skills.return_value = MagicMock()
        mock_mcp_build.return_value = MagicMock()

        # Test chaining
        result = (
            builder.with_skills(["skill1"])
            .with_mcp_servers([BigQueryMCPConfig()])
            .with_tools([MagicMock()])
        )

        assert result is builder
        assert len(builder._tools) == 3


@patch("agent.core_agent.builder.agent_builder.vertexai.Client")
@patch("agent.core_agent.builder.agent_builder.Agent")
def test_agent_builder_final_assembly(
    mock_agent_class, mock_vertex_client, mock_configs
):
    """Test that the build() method assembles the Agent correctly."""
    builder = AgentBuilder(
        agent_config=mock_configs["agent"],
        gcp_config=mock_configs["gcp"],
        auth_config=mock_configs["auth"],
    )

    agent = builder.build()

    # Verify Agent was instantiated with correct params
    args, kwargs = mock_agent_class.call_args
    assert kwargs["name"] == mock_configs["agent"].AGENT_NAME
    assert kwargs["instruction"] == mock_configs["agent"].AGENT_INSTRUCTION
    assert kwargs["planner"] is not None

    # Verify Agent was returned
    assert agent is mock_agent_class.return_value


@patch("agent.core_agent.builder.agent_builder.vertexai.Client")
@patch("agent.core_agent.builder.agent_builder.FileArtifactService")
def test_agent_builder_build_artifact_service(
    mock_artifact_service, mock_vertex_client, mock_configs
):
    """Test that the builder creates a file-backed artifact service from its configured root."""
    builder = AgentBuilder(
        agent_config=mock_configs["agent"],
        gcp_config=mock_configs["gcp"],
        auth_config=mock_configs["auth"],
    ).with_artifact_root_dir("/tmp/test-artifacts")

    artifact_service = builder.build_artifact_service()

    mock_artifact_service.assert_called_once()
    assert (
        str(mock_artifact_service.call_args.kwargs["root_dir"]) == "/tmp/test-artifacts"
    )
    assert artifact_service is mock_artifact_service.return_value


@patch("agent.core_agent.builder.agent_builder.vertexai.Client")
def test_agent_builder_build_artifact_service_requires_root_dir(
    mock_vertex_client, mock_configs
):
    """Test that artifact service creation fails until a root directory is configured."""
    builder = AgentBuilder(
        agent_config=mock_configs["agent"],
        gcp_config=mock_configs["gcp"],
        auth_config=mock_configs["auth"],
    )

    with pytest.raises(ValueError, match="Artifact root directory is not configured"):
        builder.build_artifact_service()


@patch("agent.core_agent.builder.agent_builder.vertexai.Client")
def test_agent_builder_empty_tools(mock_vertex_client, mock_configs):
    """Test that an agent can be built even with no tools."""
    builder = AgentBuilder(
        agent_config=mock_configs["agent"],
        gcp_config=mock_configs["gcp"],
        auth_config=mock_configs["auth"],
    )

    # No calls to with_skills or with_mcp_servers
    with patch("agent.core_agent.builder.agent_builder.Agent") as mock_agent:
        builder.build()
        assert mock_agent.call_args[1]["tools"] == []
