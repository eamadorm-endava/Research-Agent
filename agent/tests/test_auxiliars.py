import os
from unittest.mock import patch

from agent.core_agent.config import MCPServersConfig
from agent.core_agent.utils.auxiliars import (
    build_runtime_headers,
    get_mcp_servers_tools,
)


def test_get_mcp_servers_tools_builds_toolsets_from_url_endpoint_pairs():
    mock_env = {
        "GENERAL_TIMEOUT": "45",
        "BIGQUERY_URL": "https://bq-server.example",
        "BIGQUERY_ENDPOINT": "/mcp",
        "GCS_URL": "https://gcs-server.example",
        "GCS_ENDPOINT": "/custom-mcp",
        "DRIVE_URL": "",
    }

    with patch.dict(os.environ, mock_env, clear=True):
        config = MCPServersConfig()

    with (
        patch(
            "agent.core_agent.utils.auxiliars.StreamableHTTPConnectionParams"
        ) as mock_connection_params,
        patch("agent.core_agent.utils.auxiliars.McpToolset") as mock_toolset,
        patch(
            "agent.core_agent.utils.auxiliars.get_id_token",
            side_effect=lambda url: f"token-for-{url}",
        ),
    ):
        get_mcp_servers_tools(config)

        assert mock_connection_params.call_count == 2
        created_urls = [
            call.kwargs["url"] for call in mock_connection_params.call_args_list
        ]
        assert "https://bq-server.example/mcp" in created_urls
        assert "https://gcs-server.example/custom-mcp" in created_urls

        created_timeouts = [
            call.kwargs["timeout"] for call in mock_connection_params.call_args_list
        ]
        assert created_timeouts == [45, 45]

        assert mock_toolset.call_count == 2
        expected_auth = [
            "https://bq-server.example",
            "https://gcs-server.example",
        ]
        for call, expected_url in zip(mock_toolset.call_args_list, expected_auth):
            header_provider = call.kwargs["header_provider"]
            assert header_provider(None) == {
                "X-Serverless-Authorization": f"Bearer token-for-{expected_url}"
            }


def test_get_mcp_servers_tools_skips_empty_url_values():
    mock_env = {
        "BIGQUERY_URL": "https://bq-server.example",
        "BIGQUERY_ENDPOINT": "/mcp",
        "GCS_URL": "",
        "GCS_ENDPOINT": "/mcp",
        "DRIVE_URL": "",
    }

    with patch.dict(os.environ, mock_env, clear=True):
        config = MCPServersConfig()

    with (
        patch(
            "agent.core_agent.utils.auxiliars.StreamableHTTPConnectionParams"
        ) as mock_connection_params,
        patch("agent.core_agent.utils.auxiliars.McpToolset") as mock_toolset,
        patch(
            "agent.core_agent.utils.auxiliars.get_id_token",
            return_value="token",
        ),
    ):
        get_mcp_servers_tools(config)

    assert mock_connection_params.call_count == 1
    assert (
        mock_connection_params.call_args.kwargs["url"]
        == "https://bq-server.example/mcp"
    )
    assert mock_toolset.call_count == 1


def test_build_runtime_headers_includes_shared_google_auth_when_requested():
    with (
        patch("agent.core_agent.utils.auxiliars.get_id_token", return_value="id-token"),
        patch(
            "agent.core_agent.utils.auxiliars.get_ge_oauth_token",
            return_value="oauth-token",
        ),
    ):
        headers = build_runtime_headers(
            "https://bq-server.example",
            readonly_context=object(),
            auth_id="shared-google-auth-id",
        )

    assert headers == {
        "X-Serverless-Authorization": "Bearer id-token",
        "Authorization": "Bearer oauth-token",
    }
