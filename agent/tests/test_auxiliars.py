import os
from unittest.mock import patch

from google.adk.auth import AuthCredentialTypes

from agent.core_agent.config import MCPServersConfig
from agent.core_agent.utils.auxiliars import (
    build_google_auth_credential,
    build_google_oauth_scheme,
    build_runtime_headers,
)


def test_build_google_oauth_scheme_assigns_attributes_correctly():
    mock_env = {
        "GOOGLE_OAUTH_AUTH_URI": "https://custom.auth.uri",
        "GOOGLE_OAUTH_TOKEN_URI": "https://custom.token.uri",
    }
    with patch.dict(os.environ, mock_env, clear=True):
        config = MCPServersConfig()

    scopes = {"https://www.googleapis.com/auth/test": "test scope"}
    scheme = build_google_oauth_scheme(config, scopes)

    assert scheme.flows.authorizationCode.authorizationUrl == "https://custom.auth.uri"
    assert scheme.flows.authorizationCode.tokenUrl == "https://custom.token.uri"
    assert scheme.flows.authorizationCode.scopes == scopes


def test_build_google_auth_credential_assigns_attributes_correctly():
    mock_env = {
        "GOOGLE_OAUTH_CLIENT_ID": "test-client-id",
        "GOOGLE_OAUTH_CLIENT_SECRET": "test-client-secret",
        "GOOGLE_OAUTH_REDIRECT_URI": "http://localhost:8080/callback",
    }
    with patch.dict(os.environ, mock_env, clear=True):
        config = MCPServersConfig()

    cred = build_google_auth_credential(config)

    assert cred.auth_type == AuthCredentialTypes.OAUTH2
    assert cred.oauth2.client_id == "test-client-id"
    assert cred.oauth2.client_secret == "test-client-secret"
    assert cred.oauth2.redirect_uri == "http://localhost:8080/callback"


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


def test_build_runtime_headers_omits_authorization_if_auth_id_not_provided():
    with patch(
        "agent.core_agent.utils.auxiliars.get_id_token", return_value="id-token"
    ):
        headers = build_runtime_headers(
            "https://bq-server.example",
            readonly_context=object(),
        )

    assert headers == {"X-Serverless-Authorization": "Bearer id-token"}
