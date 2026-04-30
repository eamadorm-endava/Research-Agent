from loguru import logger
from typing import Callable, Union
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from fastapi.openapi.models import OAuth2, OAuthFlowAuthorizationCode, OAuthFlows
from google.adk.auth import AuthCredential, AuthCredentialTypes, OAuth2Auth

from ..config import BaseMCPConfig, GoogleAuthConfig
from ..security import get_ge_oauth_token, get_id_token


class MCPToolsetBuilder:
    """
    Builder class to construct MCP Toolsets for different execution environments.
    Strictly separates local ADK-managed OAuth from production Gemini Enterprise-managed OAuth.
    """

    def __init__(self, auth_config: GoogleAuthConfig) -> None:
        """Stores the shared Google OAuth configuration used when building local auth schemes.

        Args:
            auth_config: GoogleAuthConfig -> Shared OAuth credentials for local development mode.
        """
        self.auth_config = auth_config

    def _get_local_auth_params(
        self, mcp_config: BaseMCPConfig, prod_execution: bool
    ) -> dict[str, Union[OAuth2, AuthCredential, None]]:
        """Builds ADK-native OAuth schemes for local execution only; returns empty params in production.

        Args:
            mcp_config: BaseMCPConfig -> The MCP server configuration instance.
            prod_execution: bool -> Flag indicating if the execution is in production mode.

        Returns:
            dict[str, Union[OAuth2, AuthCredential, None]] -> Keys: 'auth_scheme', 'auth_credential'.
        """
        logger.debug(
            f"Evaluating local auth params for {mcp_config.__class__.__name__} (prod={prod_execution})"
        )
        if prod_execution:
            return {"auth_scheme": None, "auth_credential": None}

        has_scopes = hasattr(mcp_config, "OAUTH_SCOPES") and mcp_config.OAUTH_SCOPES
        if not has_scopes:
            return {"auth_scheme": None, "auth_credential": None}

        logger.debug("Building ADK OAuth scheme and credentials for local execution")
        auth_scheme = OAuth2(
            flows=OAuthFlows(
                authorizationCode=OAuthFlowAuthorizationCode(
                    authorizationUrl=self.auth_config.GOOGLE_OAUTH_AUTH_URI,
                    tokenUrl=self.auth_config.GOOGLE_OAUTH_TOKEN_URI,
                    scopes=mcp_config.OAUTH_SCOPES,
                )
            )
        )
        auth_credential = AuthCredential(
            auth_type=AuthCredentialTypes.OAUTH2,
            oauth2=OAuth2Auth(
                client_id=self.auth_config.GOOGLE_OAUTH_CLIENT_ID,
                client_secret=self.auth_config.GOOGLE_OAUTH_CLIENT_SECRET,
                redirect_uri=self.auth_config.GOOGLE_OAUTH_REDIRECT_URI,
            ),
        )
        return {"auth_scheme": auth_scheme, "auth_credential": auth_credential}

    def _get_header_provider_function(
        self, mcp_config: BaseMCPConfig, prod_execution: bool
    ) -> Callable[[ReadonlyContext], dict[str, str]]:
        """Creates a closure that injects security and auth tokens into MCP request headers at runtime.

        Uses a closure to capture builder-time config so the returned function satisfies
        the ADK signature: (ReadonlyContext) -> dict[str, str].

        Args:
            mcp_config: BaseMCPConfig -> The MCP server configuration instance.
            prod_execution: bool -> Flag indicating if the execution is in production mode.

        Returns:
            Callable[[ReadonlyContext], dict[str, str]] -> Runtime header provider for McpToolset.
        """
        logger.debug(f"Constructing header provider closure for {mcp_config.URL}")

        def header_provider(ctx: ReadonlyContext) -> dict[str, str]:
            """Generates runtime HTTP headers for every tool call sent to the target MCP server.

            Args:
                ctx: ReadonlyContext -> The runtime context provided by ADK.

            Returns:
                dict[str, str] -> Security and authorization headers for the MCP request.
            """
            logger.debug(f"Generating runtime headers for {mcp_config.URL}")
            # Always include X-Serverless-Authorization for Cloud Run security layer
            headers = {
                "X-Serverless-Authorization": f"Bearer {get_id_token(mcp_config.URL)}"
            }

            # Inject GE-managed OAuth token only in production for servers with Auth IDs
            if prod_execution and mcp_config.GEMINI_GOOGLE_AUTH_ID:
                headers["Authorization"] = (
                    f"Bearer {get_ge_oauth_token(ctx, mcp_config.GEMINI_GOOGLE_AUTH_ID)}"
                )
                logger.debug("Injected delegated OAuth token into Authorization header")

            return headers

        return header_provider

    def build(self, mcp_config: BaseMCPConfig, prod_execution: bool) -> McpToolset:
        """Assembles and returns a fully configured McpToolset for the target execution environment.

        Args:
            mcp_config: BaseMCPConfig -> Configuration payload for the MCP server.
            prod_execution: bool -> Flag indicating if the execution is in production mode.

        Returns:
            McpToolset -> The fully constructed MCP toolset instance.
        """
        logger.info(
            f"Building {mcp_config.__class__.__name__} MCP Toolset (prod={prod_execution})"
        )
        auth_params = self._get_local_auth_params(mcp_config, prod_execution)
        return McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=mcp_config.URL + mcp_config.ENDPOINT,
                timeout=float(mcp_config.GENERAL_TIMEOUT),
            ),
            header_provider=self._get_header_provider_function(
                mcp_config, prod_execution
            ),
            auth_scheme=auth_params["auth_scheme"],
            auth_credential=auth_params["auth_credential"],
        )
