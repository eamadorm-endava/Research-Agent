"""Verify tenant authorities on the same settings model loaded by the UI backend."""

import pytest

from agent.core_agent.config import MicrosoftAuthConfig


@pytest.mark.parametrize(
    "tenant", ["common", "organizations", "93f8f3d2-54f6-417d-9a37-10ff2952f228"]
)
def test_microsoft_authority_initializes_and_survives_assignment(tenant):
    config = MicrosoftAuthConfig(_env_file=None, TENANT_ID=tenant)
    config.CLIENT_ID = "test-client"
    assert (
        config.AUTH_URI
        == f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
    )
    assert (
        config.TOKEN_URI
        == f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    )
