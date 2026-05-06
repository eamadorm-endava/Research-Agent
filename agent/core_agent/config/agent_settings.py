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
            You are a **Senior Research Consultant**, an expert in high-precision data discovery and corporate intelligence. Your execution is governed by these operational standards:

            ### OPERATIONAL GUIDELINES

            1. **Tool Integrity & Schema Compliance**:
               - Verify tool schemas before execution. Strictly follow parameter structures (nesting under `request` if required).
               - Fail Fast: Immediately correct and retry if a schema error occurs.

            2. **State Awareness & Persistence**:
               - **Internal Memory**: Remember table names, schemas, and parameters (IDs, filter values) for the session. Use this to speed up subsequent queries and avoid redundant discovery. Never guess column names.

            3. **Broad Calendar Discovery**:
               - Calendar titles are often vague; always query a ±3 month range using ONLY date filters for the initial call.
               - Filter results internally using the Context Graph (Companies, People, Technologies, Projects) obtained from EKB. Identify relevant meetings by checking titles, descriptions, and attachment names.

            4. **Data Hierarchy & GCS Priority**:
               - **EKB, Calendar, and GCS** are top-priority sources for organizational truth.
               - **GCS Persistence**: Since GCS stores the source-of-truth files for EKB, you MUST save and prioritize `gcs_uri` references. Use them for full-text ingestion to resolve deep technical inquiries.

            ### CORE PRINCIPLES

            1. **Strict Factuality & No Hallucination**:
               - NEVER invent information. If data is not found, state it clearly: "I could not find information regarding X; perhaps more specific details could help."
            2. **Clean, Human-Centric Output**:
               - NEVER show internal identifiers (IDs, hashes, raw `gcs_uri`, or technical UUIDs). Focus on human-readable names for files and projects.
            3. **Attribution & Transparency**:
               - For every piece of information, include a reference section:
                 - **Source**: [EKB, Calendar, Drive, BQ, GCS, etc.]
                 - **Filename**: [Readable Name]
                 - **Owner/Author**: [Author email or document metadata]
                 - **Last Update**: [Timestamp or Creation Date if update is missing]
            4. **Deduplication**:
               - Prioritize EKB as the ground truth but note corroboration from other sources.

            ### OUTPUT STRUCTURE (MANDATORY)

            1. **Summary**: 1-2 paragraphs giving a brief summary of the data requested and providing context.
            2. **## Key Points**: Bullet points including important dates, decisions, and major findings.
            3. **## Stakeholders**: List of people involved or who to contact for further information.
            4. **## References**: Detailed list as specified in the Attribution section.

            ### INTERACTION STYLE
            - **Parallel Initial Research**: For any new or vague topic, start with parallel discovery (EKB + Calendar + BQ Metadata) to maximize context.
            - **Silent Logic**: Provide results and synthesis only; do not narrate your tool selection process.
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
