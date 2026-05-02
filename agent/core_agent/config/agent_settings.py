from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field
from typing import Annotated, Optional


class GCPConfig(BaseSettings):
    """Holds configuration values for GCP services, enabling future cloud provider portability."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
    )

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
    PROD_EXECUTION: Annotated[
        bool,
        Field(
            default=True,
            description="Flag to determine if the agent is running in a production environment. Defaults to True, override in local .env to False.",
            validation_alias=AliasChoices("PROD_EXECUTION", "IS_DEPLOYED"),
        ),
    ]
    ARTIFACT_BUCKET: Annotated[
        str,
        Field(
            default="ai_agent_landing_zone",
            description="GCS Bucket where the user-uploaded artifacts will be stored.",
        ),
    ]


class AgentConfig(BaseSettings):
    """Holds configuration values for the ADK agent: model, generation, retry, and system prompt."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
    )

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
        Optional[str],
        Field(
            default=None,
            description="The final ID of the Model Armor template (e.g., 'security-template'). The full resource path (projects/.../templates/...) is constructed dynamically using the project and region settings. When None, Model Armor screening is disabled.",
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
            default="core_agent",
            description="Name of the agent",
        ),
    ]
    EKB_PIPELINE_URL: Annotated[
        str,
        Field(
            default="mock-pipeline-url",
            description="The URL of the Enterprise Knowledge Base ingestion pipeline service.",
            validation_alias=AliasChoices("EKB_PIPELINE_URL"),
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
            You are an AI Agent expert in Data Analysis and Corporate Intelligence, serving as a **Senior Research Consultant**. 
            Your primary objective is to search, synthesize, and summarize information scattered across various company data 
            sources using a high-precision, hybrid discovery protocol.

            ### AVAILABLE DATA SOURCES
            1. **Enterprise Knowledge Base (EKB)**: Primary source for verified project data, stored in BigQuery and GCS.
            2. **Google Drive**: Ideal for searching personal or team documents, presentations, and spreadsheets.
            3. **Google Cloud Storage (GCS)**: For large flat files or data backups.
            4. **BigQuery (BQ)**: For structured data and tabular databases.

            ### CORE STRATEGY: HYBRID DISCOVERY (EKB FIRST)
            You must prioritize the EKB. When a user asks for research or analysis, follow this 3-Phase protocol:

            1. **PHASE 1: SEMANTIC ANCHORING**
               - Call `ekb_semantic_search` to find conceptually relevant chunks.
               - **Extraction**: Identify key identifiers from the results: `project_id`, `domain`, `document_id`, and other relevant metadata.
            
            2. **PHASE 2: METADATA-BASED SQL PIVOT**
               - Use the identifiers from Phase 1 to call `execute_query` and expand the search to all documents associated with that project or domain.
               - Evaluate document summaries (`description`) in the metadata.

            3. **PHASE 3: LONG CONTEXT DEEP ANALYSIS**
               - If metadata is insufficient, select up to **10** GCS URIs.
               - Import these files using `import_gcs_to_artifact` and load them via `load_artifacts` for full-text analysis.

            ### MANDATORY TOOL CONSTRAINTS
            You MUST include all required parameters to ensure successful tool execution.

            ### OUTPUT STANDARDS
            Structure your final response as follows:
            # Summary
            [1-2 paragraphs of context]
            # Key Points
            - [Key insight]
            - [Specific data point]
            # Stakeholders
            - [List of persons/roles identified]
            # Data Sources
            - [Filename] (Last Update: [Date], Owner: [Email])

            ### INTERACTION & PRIVACY
            - **Personal Search**: After EKB analysis, always ask if the user wants to search their personal data for additional context. If so, ask if they have a preference (Drive, personal buckets, or private BQ tables) to optimize the search time.
            - **Clean Output**: NEVER show internal identifiers (`file_id`, raw `document_id`, hashes). Use human-readable names.
            - **Silent Execution**: Do not output internal reasoning or intermediate results.
            """,
            description="Agent's System Prompt",
        ),
    ]


class GoogleAuthConfig(BaseSettings):
    """Holds shared Google OAuth 2.0 credentials used across all MCP server connections."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
    )

    GOOGLE_OAUTH_CLIENT_ID: Annotated[
        str,
        Field(
            default="mock-oauth-client-id",
            description="Shared OAuth 2.0 Client ID for Google APIs used by the agent.",
        ),
    ]
    GOOGLE_OAUTH_CLIENT_SECRET: Annotated[
        str,
        Field(
            default="mock-oauth-client-secret",
            description="Shared OAuth 2.0 Client Secret for Google APIs used by the agent.",
        ),
    ]
    GOOGLE_OAUTH_REDIRECT_URI: Annotated[
        str,
        Field(
            default="http://localhost:8000/dev-ui",
            description="Shared OAuth 2.0 Redirect URI for Google APIs used by the agent.",
        ),
    ]
    GOOGLE_OAUTH_AUTH_URI: Annotated[
        str,
        Field(
            default="https://accounts.google.com/o/oauth2/v2/auth",
            description="Shared OAuth 2.0 authorization URL for Google APIs used by the agent.",
        ),
    ]
    GOOGLE_OAUTH_TOKEN_URI: Annotated[
        str,
        Field(
            default="https://oauth2.googleapis.com/token",
            description="Shared OAuth 2.0 token URL for Google APIs used by the agent.",
        ),
    ]


# Global configuration instances
GCP_CONFIG = GCPConfig()
AGENT_CONFIG = AgentConfig()
GOOGLE_AUTH_CONFIG = GoogleAuthConfig()
