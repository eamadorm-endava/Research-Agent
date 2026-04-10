from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field, field_validator, ValidationInfo
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
            default=0.3,
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
    INCLUDE_THOUGHTS: Annotated[
        bool,
        Field(
            default=False,
            description="Indicates whether to include thoughts in the response. If true, thoughts are returned only if the model supports thought and thoughts are available.",
        ),
    ]
    THINKING_BUDGET: Annotated[
        int,
        Field(
            default=-1,
            description="Indicates the thinking budget in tokens. 0 is DISABLED. -1 is AUTOMATIC. The default values and allowed ranges are model dependent.",
        ),
    ]
    AGENT_INSTRUCTION: Annotated[
        str,
        Field(
            default="""
            You are an AI Agent expert in Data Analysis and Corporate Intelligence. Your primary objective is to search, 
            synthesize, and summarize information scattered across various company data sources and present it to the user 
            in a clear, actionable format, completely free of internal technical jargon.

            ### AVAILABLE DATA SOURCES
            You have access to the following tools and sources:
            1. Google Drive: Ideal for searching documents, presentations, spreadsheets, and plain text files.
            2. Google Cloud Storage (GCS): Ideal for searching Data Lakes, large flat files, or data backups.
            3. BigQuery (BQ): Ideal for searching structured data, financial metrics, transactional records, and tabular databases.

            ### MANDATORY EXECUTION FLOW
            You must strictly follow this workflow for every interaction:

            STEP 1: EVALUATION AND CLARIFICATION
            If the user provides a vague or very general prompt (e.g., "Give me everything we have on company X"), 
            DO NOT start searching immediately.
            - Ask the user if they want to search across all available sources or only a specific one (GCS, BQ, Drive).
            - Make a recommendation based on their request. For example, if they ask for "files" or "documents", prioritize 
              and suggest Drive and GCS; if they ask for "data" or "metrics", suggest BQ.

            STEP 2: SEARCH STRATEGY (INITIAL QUERIES)
            Once the user confirms (or if the initial prompt was specific enough), you must:
            - Generate exactly 4 different keywords related to the request.
            - Perform 4 independent searches using your tools, one for each keyword.
            - In this initial stage, filter by focusing on metadata matches: file names, folder names, and table names.
            - Refine the search by applying recency filters (prioritize the most recently updated or newly created documents).

            STEP 3: READING AND SYNTHESIS
            - Based on the metadata obtained in Step 2, select ONLY the top 3 or 4 most relevant documents/tables.
            - Read and extract the content of those top 3 or 4 items.
            - Synthesize the information to generate a report. The report must be written in the same language the user
              is using to communicate with you.

            ### STRICT RESTRICTIONS
            - NEVER include internal identifiers that the user would not understand. It is STRICTLY FORBIDDEN to 
              show `file_id`, `user_id`, `folder_id`, `project_id`, raw API URLs, or hashes.
            - When referencing sources, use ONLY human-readable names (file names, folder names, table names).

            ### SILENT EXECUTION (NO INTERNAL THOUGHTS)
            - DO NOT output any of your internal reasoning, thoughts, action planning, or intermediate tool results to the user.
            - Your internal process (generating keywords, evaluating metadata, reading files) must remain completely hidden.
            - The ONLY text you are allowed to output to the user is either:
              1. Clarification questions from step 1.
              2. The final response from step 3.

            ### FINAL OUTPUT FORMAT
            Be brief and consice if the user ask for a simple answer. Always answer in the same language the user is asking.
            If the user ask for a summary of an specific topic, your final response to the user must be structured 
            using the following Markdown format. **IMPORTANT: Translate the headers (## Executive Summary, 
            ## Key Points, etc.) to the same language the user is using.**

            ## Executive Summary: [Search Topic]
            [A brief 1-2 paragraph context about the findings, if necessary to understand the information].

            ## Key Points
            - [Key point 1 extracted from the documents]
            - [Key point 2 extracted from the documents]
            - [Key point N...]

            ## Stakeholders Involved
            - [Name, Role, or Department of the people involved found in the texts]

            ## Decisions Made
            - [Documented decision 1]
            - [Documented decision 2]

            ## Last Project Update
            [Date of the last update or modification based on the metadata of the most recent documents].

            ## Information Sources
            - [File Name 1 / Folder / BQ Table]
            - [File Name 2 / Folder / BQ Table]
            """,
            description="Agent's System Prompt",
        ),
    ]
    MEETING_SUMMARY_FOLDER: Annotated[
        str,
        Field(
            default="AI Meetings Summaries",
            description="Folder where meeting summaries are stored in Drive",
        ),
    ]
    MEETING_SUMMARY_FILENAME_PATTERN: Annotated[
        str,
        Field(
            default="YYYY-MM-DD - meeting-name - Summary.docx",
            description="Pattern used to name generated meeting summary documents",
        ),
    ]


class DriveScopes(StrEnum):
    """
    Enum for Google Drive OAuth scopes.
    """

    DRIVE = "https://www.googleapis.com/auth/drive"


class BigQueryScopes(StrEnum):
    """
    Enum for Google BigQuery OAuth scopes.
    """

    BIGQUERY = "https://www.googleapis.com/auth/bigquery"


class CalendarScopes(StrEnum):
    """
    Enum for Google Calendar OAuth scopes.
    """

    CALENDAR_READONLY = "https://www.googleapis.com/auth/calendar.events.readonly"
    MEET_READONLY = "https://www.googleapis.com/auth/meetings.space.readonly"


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
            default="http://localhost:8080",
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
    GCS_URL: Annotated[
        str,
        Field(
            default="http://localhost:8082",
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
    CALENDAR_URL: Annotated[
        str,
        Field(
            default="http://localhost:8083",
            description="Google Calendar MCP Server URL, uses a streamable http connection",
        ),
    ]
    CALENDAR_ENDPOINT: Annotated[
        str,
        Field(
            default="/mcp",
            description="Google Calendar MCP Server Endpoint",
        ),
    ]
    GOOGLE_OAUTH_CLIENT_ID: Annotated[
        str,
        Field(
            default="",
            description="Shared OAuth 2.0 Client ID for Google APIs used by the agent.",
            validation_alias=AliasChoices(
                "GOOGLE_OAUTH_CLIENT_ID", "DRIVE_OAUTH_CLIENT_ID"
            ),
        ),
    ]
    GOOGLE_OAUTH_CLIENT_SECRET: Annotated[
        str,
        Field(
            default="",
            description="Shared OAuth 2.0 Client Secret for Google APIs used by the agent.",
            validation_alias=AliasChoices(
                "GOOGLE_OAUTH_CLIENT_SECRET", "DRIVE_OAUTH_CLIENT_SECRET"
            ),
        ),
    ]
    GOOGLE_OAUTH_REDIRECT_URI: Annotated[
        str,
        Field(
            default="http://localhost:8000/dev-ui",
            description="Shared OAuth 2.0 Redirect URI for Google APIs used by the agent.",
            validation_alias=AliasChoices(
                "GOOGLE_OAUTH_REDIRECT_URI", "DRIVE_OAUTH_REDIRECT_URI"
            ),
        ),
    ]
    GOOGLE_OAUTH_AUTH_URI: Annotated[
        str,
        Field(
            default="https://accounts.google.com/o/oauth2/v2/auth",
            description="Shared OAuth 2.0 authorization URL for Google APIs used by the agent.",
            validation_alias=AliasChoices(
                "GOOGLE_OAUTH_AUTH_URI", "DRIVE_OAUTH_AUTH_URI"
            ),
        ),
    ]
    GOOGLE_OAUTH_TOKEN_URI: Annotated[
        str,
        Field(
            default="https://oauth2.googleapis.com/token",
            description="Shared OAuth 2.0 token URL for Google APIs used by the agent.",
            validation_alias=AliasChoices(
                "GOOGLE_OAUTH_TOKEN_URI", "DRIVE_OAUTH_TOKEN_URI"
            ),
        ),
    ]
    GEMINI_GOOGLE_AUTH_ID: Annotated[
        str,
        Field(
            default="mock-ge-auth-id",
            description="The ID of the shared delegated Google OAuth authorization resource registered in Gemini Enterprise and reused by MCP tool calls."
            " Check: https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent?hl=en#add-authorization-resource",
            validation_alias=AliasChoices(
                "GEMINI_GOOGLE_AUTH_ID", "GEMINI_DRIVE_AUTH_ID"
            ),
        ),
    ]
    BIGQUERY_OAUTH_SCOPES: Annotated[
        Union[dict[str, str], list[BigQueryScopes]],
        Field(
            default=[BigQueryScopes.BIGQUERY],
            description="OAuth scopes requested by the agent when authenticating to the BigQuery MCP server.",
        ),
    ]
    DRIVE_OAUTH_SCOPES: Annotated[
        Union[dict[str, str], list[DriveScopes]],
        Field(
            default=[DriveScopes.DRIVE],
            description="OAuth scopes requested by the agent when authenticating to the Drive MCP server.",
        ),
    ]
    CALENDAR_OAUTH_SCOPES: Annotated[
        Union[dict[str, str], list[CalendarScopes]],
        Field(
            default=[
                CalendarScopes.CALENDAR_READONLY,
                CalendarScopes.MEET_READONLY,
            ],
            description="OAuth scopes requested by the agent when authenticating to the Calendar MCP server.",
        ),
    ]

    @field_validator(
        "BIGQUERY_OAUTH_SCOPES",
        "CALENDAR_OAUTH_SCOPES",
        "DRIVE_OAUTH_SCOPES",
        mode="after",
    )
    @classmethod
    def validate_oauth_scopes(
        cls,
        v: Union[
            list[Union[BigQueryScopes, CalendarScopes, DriveScopes]], dict[str, str]
        ],
        info: ValidationInfo,
    ) -> dict[str, str]:
        if isinstance(v, dict):
            return v

        service_name = (
            info.field_name.replace("_OAUTH_SCOPES", "").lower().replace("_", " ")
        )
        return {scope.value: f"google {service_name} access" for scope in v}
