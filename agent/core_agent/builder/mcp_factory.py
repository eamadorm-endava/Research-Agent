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

    def __init__(self, auth_config: GoogleAuthConfig):
        self.auth_config = auth_config

    def _get_local_auth_params(
        self, mcp_config: BaseMCPConfig, prod_execution: bool
    ) -> dict[str, Union[OAuth2, AuthCredential, None]]:
        """Builds ADK-native OAuth schemes only for local execution with servers requiring OAuth.
        In production, these parameters are omitted as Gemini Enterprise handles the flow.

        Args:
            mcp_config (BaseMCPConfig): The MCP server configuration instance.
            prod_execution (bool): Flag indicating if the execution is in production mode.

        Returns:
            dict[str, Union[OAuth2, AuthCredential, None]]: A dictionary containing 'auth_scheme'
                and 'auth_credential' (both Optional).
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
        """Creates a runtime header provider function that injects security and auth tokens into MCP requests.

        Reasoning: ADK's McpToolset expects a provider signature of (ReadonlyContext) -> dict.
        Since we need the builder-time configuration (mcp_config, prod_execution) to generate
        correct headers, we use a closure to 'capture' these variables in the provider scope.

        Args:
            mcp_config (BaseMCPConfig): The MCP server configuration instance.
            prod_execution (bool): Flag indicating if the execution is in production mode.

        Returns:
            Callable[[ReadonlyContext], dict[str, str]]: A closure that ADK will call at runtime.
        """
        logger.debug(f"Constructing header provider closure for {mcp_config.URL}")

        def header_provider(ctx: ReadonlyContext) -> dict[str, str]:
            """Generates runtime HTTP headers using the captured configuration and current context.
            Injected into every tool call sent to the target MCP server.

            Args:
                ctx (ReadonlyContext): The runtime context provided by ADK.

            Returns:
                dict[str, str]: A dictionary containing security and authorization headers.
            """
            logger.debug(f"Generating runtime headers for {mcp_config.URL}")
            # Always include X-Serverless-Authorization for Cloud Run security layer
            headers = {
                "X-Serverless-Authorization": f"Bearer {get_id_token(mcp_config.URL)}"
            }

            # Inject GE-managed OAuth token only in production for servers with Auth IDs
            if prod_execution and mcp_config.GEMINI_GOOGLE_AUTH_ID:
                token = get_ge_oauth_token(ctx, mcp_config.GEMINI_GOOGLE_AUTH_ID)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    logger.debug(
                        "Injected delegated OAuth token into Authorization header"
                    )

            return headers

        return header_provider

    def build(self, mcp_config: BaseMCPConfig, prod_execution: bool) -> McpToolset:
        """Assembles and returns the final McpToolset configured for the target environment.
        Uses the internal helper methods to construct auth params and header providers.

        Args:
            mcp_config (BaseMCPConfig): The configuration payload for the MCP server.
            prod_execution (bool): Flag indicating if the execution is in production mode.

        Returns:
            McpToolset: The fully constructed MCP toolset instance.
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
            ),  # self._get_header_provider_function returns a function with a signature of (ReadonlyContext) -> dict
            auth_scheme=auth_params["auth_scheme"],
            auth_credential=auth_params["auth_credential"],
        )
