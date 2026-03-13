from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Annotated


class GCPConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
    )
    """
    Class that holds configuration values for GCP services. Allowing to, in any future, change the
    cloud provider or the way to access the secrets.
    """

    PROJECT_ID: Annotated[
        str,
        Field(
            default="dummy-gcp-project-id",
            description="GCP Project ID",
        ),
    ]
    REGION: Annotated[
        str,
        Field(
            default="dummy-gcp-region",
            description="GCP Region where most of the services will be deployed",
        ),
    ]


class AgentConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
    )
    """
    Class that holds configuration values for the agent, it requires to assign
    parameters after initialization.
    """

    MODEL_NAME: Annotated[
        str,
        Field(
            default="gemini-2.5-flash",
            description="Name of the Gemini model to use.",
        ),
    ]
    TEMPERATURE: Annotated[
        float,
        Field(
            default=0.5,
            description="Controls randomness in model output: lower values make responses more focused, higher values more creative.",
            ge=0,
            le=1,
        ),
    ]
    TOP_P: Annotated[
        float,
        Field(
            default=0.95,
            description="Manage the randomness of the LLM ouput. Establish a probability threshold",
            ge=0,
            le=1,
        ),
    ]
    TOP_K: Annotated[
        float,
        Field(
            default=40,
            description="Determines how many of the most likely tokens should be considered when generating a response.",
        ),
    ]
    MAX_OUTPUT_TOKENS: Annotated[
        int,
        Field(
            default=10_000,
            description="Controls the maximum number of tokens generated in a single call to the LLM model",
        ),
    ]
    SEED: Annotated[
        int,
        Field(
            default=1080,
            description="If seed is set, the model makes a best effort to provide the same response for repeated requests. By default, a random number is used.",
        ),
    ]
    MODEL_ARMOR_TEMPLATE_ID: Annotated[
        str,
        Field(
            default="dummy-template-id",
            description="Model Armor Template ID",
        ),
    ]
    RETRY_ATTEMPTS: Annotated[
        int,
        Field(
            default=5,
            description="Number of attempts to retry the request in case of failure.",
        ),
    ]
    RETRY_INITIAL_DELAY: Annotated[
        int,
        Field(
            default=1,
            description="Initial delay in seconds to retry the request in case of failure.",
        ),
    ]
    RETRY_EXP_BASE: Annotated[
        int,
        Field(
            default=3,
            description="Exponential base to retry the request in case of failure.",
        ),
    ]
    RETRY_MAX_DELAY: Annotated[
        int,
        Field(
            default=90,
            description="Maximum delay in seconds to retry the request in case of failure.",
        ),
    ]


class MCPServersConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
    )
    """
    Class that holds configuration values for MCP servers.
    """

    GENERAL_TIMEOUT: Annotated[
        int,
        Field(
            default=60,
            description="Timeout in seconds for MCP servers.",
        ),
    ]
    BIGQUERY_URL: Annotated[
        str,
        Field(
            default="https://bigquery-mcp-server-753988132239.us-central1.run.app",
            description="BigQuery MCP Server URL, uses a streamable http connection",
        ),
    ]
    BIGQUERY_ENDPOINT: Annotated[
        str,
        Field(
            default="/mcp",
            description="BigQuery MCP Server Endpoint",
        ),
    ]
    DRIVE_URL: Annotated[
        str,
        Field(
            default="http://localhost:8081",
            description="Google Drive MCP Server base URL.",
        ),
    ]
    DRIVE_ENDPOINT: Annotated[
        str,
        Field(
            default="/mcp",
            description="Google Drive MCP Server endpoint path.",
        ),
    ]
    DRIVE_DELEGATED_TOKEN_HEADER: Annotated[
        str,
        Field(
            default="x-drive-access-token",
            description="Header used to forward the user's delegated OAuth access token to the Drive MCP server.",
        ),
    ]
    BIGQUERY_DISABLE_ID_TOKEN_AUTH: Annotated[
        bool,
        Field(
            default=False,
            description="Disable Cloud Run ID-token auth for the BigQuery MCP server, useful for local development.",
        ),
    ]
    DRIVE_DISABLE_ID_TOKEN_AUTH: Annotated[
        bool,
        Field(
            default=False,
            description="Disable Cloud Run ID-token auth for the Drive MCP server, useful for local development.",
        ),
    ]
    DRIVE_MCP_AUTH_MODE: Annotated[
        str,
        Field(
            default="none",
            description="Optional authentication mode for the Drive MCP server itself. Supported values: none, api_key_header, oauth2_client_credentials.",
        ),
    ]
    DRIVE_MCP_AUTH_HEADER_NAME: Annotated[
        str,
        Field(
            default="Authorization",
            description="Header name to use when DRIVE_MCP_AUTH_MODE=api_key_header.",
        ),
    ]
    DRIVE_MCP_AUTH_TOKEN: Annotated[
        str,
        Field(
            default="",
            description="Static token value to send when DRIVE_MCP_AUTH_MODE=api_key_header. When using the Authorization header include the Bearer prefix if your gateway expects it.",
        ),
    ]
    DRIVE_MCP_OAUTH_CLIENT_ID: Annotated[
        str,
        Field(
            default="",
            description="OAuth2 client ID for MCP-server authentication when DRIVE_MCP_AUTH_MODE=oauth2_client_credentials.",
        ),
    ]
    DRIVE_MCP_OAUTH_CLIENT_SECRET: Annotated[
        str,
        Field(
            default="",
            description="OAuth2 client secret for MCP-server authentication when DRIVE_MCP_AUTH_MODE=oauth2_client_credentials.",
        ),
    ]
    DRIVE_MCP_OAUTH_TOKEN_URL: Annotated[
        str,
        Field(
            default="",
            description="OAuth2 token URL for MCP-server authentication. Leave blank to rely on ADK discovery if your MCP gateway exposes RFC 8414 metadata.",
        ),
    ]
    DRIVE_MCP_OAUTH_AUTH_URL: Annotated[
        str,
        Field(
            default="",
            description="Optional OAuth2 authorization URL for MCP-server authentication. Mainly useful for future interactive flows.",
        ),
    ]
    DRIVE_MCP_OAUTH_SCOPES: Annotated[
        str,
        Field(
            default="",
            description="Comma-separated OAuth2 scopes for MCP-server authentication.",
        ),
    ]
