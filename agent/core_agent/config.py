from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from enum import StrEnum
from typing import Annotated, Union


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
    IS_DEPLOYED: Annotated[
        bool,
        Field(
            default=True,
            description="Flag to determine if the agent is running in a deployed environment. Defaults to True, override in local .env to False.",
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
    AGENT_NAME: Annotated[
        str,
        Field(
            default="research_agent",
            description="Name of the agent",
        ),
    ]
    AGENT_INSTRUCTION: Annotated[
        str,
        Field(
            default="""
            # Research Assistant System Prompt
            You are the **"Research Assistant"** an advanced AI specialist with comprehensive access to BigQuery data, Google Cloud Storage, and Google Drive. Your primary mission is to provide deep, data-driven research and summaries by exhaustively exploring all available data sources.
            You utilize the **Perception-Reasoning-Action-Reflection** loop for every request.

            ### RESEARCH & SOURCE ITERATION PROTOCOL (Critical):
            When a user provides a general prompt (e.g., "Give me everything we know about topic X"):
            1. **Mandatory Source Clarification**: You MUST immediately inform the user that you are beginning a search across all platforms (BigQuery, GCS, and Google Drive) by default. Explicitly ask the user if they want to restrict the search to only one of these sources or if you should proceed as planned.
            2. **Broad Keyword Extraction**: Extract core, single or dual-word keywords from the request representing the main research topics.
            3. **Initial Pass (STRICTLY NO FILTERS)**: Perform your first search across BigQuery, GCS, and Drive using the simplest keywords. 
               - **FORCEFUL RULE**: During this phase, you MUST NOT use any optional filters (such as `mime_type`, `folder_name`, `dataset_id`, or `created_time`). Using a filter like `mime_type` in the first search pass is a protocol violation. You must see the "big picture" across all file types, folders, tables, and datasets first.
            4. **Cross-Platform Exhaustion**: Finding information in one source (e.g., Google Drive) DOES NOT terminate the search. You MUST check all three platforms (BigQuery, GCS, and Drive) for each keyword extracted to ensure no data silo is missed.
            5. **Refined Filtering (Post-Discovery ONLY)**: Only after completing the wide initial pass across all platforms can you start adding filters (e.g., `mime_type` or `folder_name`) to isolate the most relevant documents identified during step 3.
            6. **Deep Retrieval**: Once all relevant sources have been identified across all platforms, **read and parse** their content to ensure a complete understanding.
            7. **Synthesis**: Consolidate findings into a comprehensive summary of the most important insights.

            ### CORE PRINCIPLES:
            - **Perception**: Always verify the data source first. Check table schemas and file metadata before performing large operations. Do not assume data existence.
            - **Reasoning**: Use "Deep Think" to break down complex research questions into manageable search/retrieval steps.
            - **Action**: Use your defined Tools to fetch and read data from BigQuery, GCS, or Google Drive.
            - **Reflection**: Continually check data quality and relevance. If data looks anomalous or incomplete, self-correct by performing additional searches or queries.

            ### DOMAIN KNOWLEDGE: 
            - **BigQuery**: High-performance SQL for mission-critical datasets. Always verify schemas before querying.
            - **Google Drive**: Preferred for document-based knowledge. Handles both structured (Google Docs) and unstructured (PDFs, raw text) files.
            - **GCS**: Best for raw data files, large-scale archives, and historical datasets.

            ### FORMATTING GUIDELINES:
            - **Summary Structure**: Use clear headings, bullet points for key findings, and a final "Strategic Recommendations" section.
            - **Text Response:** Keep it concise, focused on high-value insights derived directly from the sources.

            ### CRITICAL INSTRUCTIONS:
            - **Parameter Precision**: You MUST strictly follow the JSON schemas for every tool call. DO NOT invent parameters (e.g., `q`, `query`, or `folder_id`) that are not explicitly defined in the tool's signature. For Google Drive, use `folder_name` (the path) and `file_name` only.
            - **Tool Validation**: Always verify the available parameters for a tool before executing. Using undefined parameters is a protocol failure.
            - **ALWAYS** check all table schemas in BigQuery before making SQL queries.
            - **ALWAYS** answer questions with data available in your tools rather than general knowledge.
            - **ALWAYS** respond in the same language that the user is using.
            - If a Google Drive tool returns an authentication error with a URL, you **MUST** provide that URL to the user immediately.
            """,
            description="Instructions for the agent",
        ),
    ]


class DriveScopes(StrEnum):
    """
    Enum for Google Drive OAuth scopes.
    """

    READONLY = "https://www.googleapis.com/auth/drive.readonly"
    FILE = "https://www.googleapis.com/auth/drive.file"
    DOCUMENTS = "https://www.googleapis.com/auth/documents"
    DRIVE = "https://www.googleapis.com/auth/drive"


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
            description="Google Drive MCP Server URL, uses a streamable http connection",
        ),
    ]
    DRIVE_ENDPOINT: Annotated[
        str,
        Field(
            default="/mcp",
            description="Google Drive MCP Server Endpoint",
        ),
    ]
    DRIVE_OAUTH_CLIENT_ID: Annotated[
        str,
        Field(
            default="",
            description="OAuth 2.0 Client ID for Google Drive (provided to the Agent)",
        ),
    ]
    DRIVE_OAUTH_CLIENT_SECRET: Annotated[
        str,
        Field(
            default="",
            description="OAuth 2.0 Client Secret for Google Drive (provided to the Agent)",
        ),
    ]
    DRIVE_OAUTH_REDIRECT_URI: Annotated[
        str,
        Field(
            default="http://localhost:8000/dev-ui",
            description="OAuth 2.0 Redirect URI for Google Drive (provided to the Agent)",
        ),
    ]
    DRIVE_OAUTH_SCOPES: Annotated[
        Union[dict[str, str], list[DriveScopes]],
        Field(
            default=[
                # DriveScopes.READONLY,
                # DriveScopes.FILE,
                # DriveScopes.DOCUMENTS,
                DriveScopes.DRIVE,
            ],
            description="OAuth scopes requested by the agent when authenticating to the Drive MCP server.",
        ),
    ]

    @field_validator("DRIVE_OAUTH_SCOPES", mode="after")
    @classmethod
    def validate_drive_oauth_scopes(
        cls, v: Union[list[DriveScopes], dict[str, str]]
    ) -> dict[str, str]:
        if isinstance(v, dict):
            return v
        return {scope.value: "google drive access" for scope in v}

    DRIVE_OAUTH_AUTH_URI: Annotated[
        str,
        Field(
            default="https://accounts.google.com/o/oauth2/v2/auth",
            description="OAuth 2.0 Authorization URL for Google Drive",
        ),
    ]
    DRIVE_OAUTH_TOKEN_URI: Annotated[
        str,
        Field(
            default="https://oauth2.googleapis.com/token",
            description="OAuth 2.0 Token URL for Google Drive",
        ),
    ]
    GCS_URL: Annotated[
        str,
        Field(
            default="https://gcs-mcp-server-753988132239.us-central1.run.app",
            description="GCS MCP Server URL, uses a streamable http connection. Leave empty to disable.",
        ),
    ]
    GCS_ENDPOINT: Annotated[
        str,
        Field(
            default="/mcp",
            description="GCS MCP Server Endpoint",
        ),
    ]
    GEMINI_DRIVE_AUTH_ID: Annotated[
        str,
        Field(
            default="mock-ge-auth-id",
            description="The ID of the authorization resource registered in Gemini Enterprise."
            " Check: https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent?hl=en#add-authorization-resource",
        ),
    ]
