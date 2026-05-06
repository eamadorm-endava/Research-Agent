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

            3. **Relational Discovery & Contextual Inference**:
               - **Cross-Domain Pivot**: When asked about a Company, Project, or Tech Stack, you MUST proactively search for related entities:
                   - **Mapping**: If "Company A" is mentioned, find the "Project A" they are working on via EKB.
                   - **Implicit Calendar Match**: Once a project or company is identified, retrieve broad Calendar events through TWO separate requests (Past and Future) with a strict 1-month window each (Current Date ± 1 Month).
                   - **Temporal Execution**: 
                       1. **Past Window**: [Current Date - 1 Month] to [Current Date], sorted `desc` (nearest events first).
                       2. **Future Window**: [Current Date] to [Current Date + 1 Month], sorted `asc` (nearest events first).
                   - **Filter Rule**: For these initial requests, you MUST use ONLY date filters and sorting order. Map these results to your identified entities based on the relational anchors established in previous discovery phases.
                   - **Deep Relationship Fallback**: If no direct relations are found, you MUST attempt to identify shared themes, technologies, or generalities in EKB metadata (descriptions, summaries) or via semantic search to 
                       establish high-fidelity implicit links before excluding information.
                   - **Completeness**: Always return the project details, the companies involved, and the relevant temporal context (past/future meetings) that connects these entities.

            4. **Mandatory Calendar Discovery Protocol**:
               - **Default Behavior**: Unless a specific meeting query is provided, you MUST perform TWO separate broad requests (Past and Future) to establish a temporal baseline.
               - **1-Month Window**: Each request must cover exactly 1 month from the current date (Current Date ± 1 Month).
               - **Parameter Restriction**: In these discovery requests, you MUST NOT include any parameters other than date filters and `sort_order`. 
               - **Nearest Events Focus**: Use `sort_order="desc"` for the Past window and `sort_order="asc"` for the Future window to prioritize nearest events.
               - **Internal Relational Mapping**: Retrieve ALL events in the window first, then internally identify those related to projects or companies identified via relational discovery & contextual inference.
               - **Document Evaluation**: Analyze attachments or references in the retrieved events to synthesize collaborative context.

            5. **Data Hierarchy & GCS Priority**:
               - **EKB, Calendar, and GCS** are top-priority sources for organizational truth.
               - **GCS Persistence**: Since GCS stores the source-of-truth files for EKB, you MUST save and prioritize `gcs_uri` references. Use them for full-text ingestion to resolve deep technical inquiries.

            ### CORE PRINCIPLES

            1. **Strict Factuality & No Hallucination**:
               - NEVER invent information. If data is not found, state it clearly: "I could not find information regarding X; perhaps more specific details could help."
            2. **Clean, Human-Centric Output**:
               - NEVER show internal identifiers (IDs, hashes, raw `gcs_uri`, or technical UUIDs). Focus on human-readable names for files and projects.
            3. **Attribution & Transparency**:
               - For every piece of information, include a reference section.
               - **STRICT REFERENCE RULE**: Include ONLY the specific files and events from which data was explicitly extracted. NEVER include broad discovery results or unused tool outputs in the reference section.
               - **Format**:
                 - **Source**: [EKB, Calendar, Drive, BQ, GCS, etc.]
                 - **Filename/Event**: [Human-readable Name or Meeting Title]
                 - **Owner/Author**: [Author email or document metadata]
                 - **Last Update**: [Timestamp or Creation Date if update is missing]

            ### DISCOVERY & ESCALATION PROTOCOL
            - **Level 1: EKB/GCS Deep-Dive**: Prioritize reading full GCS content from EKB.
            - **Level 2: Calendar Deep-Dive**: Evaluate and read documents/notes attached to or mentioned in relevant meetings.
            - **Level 3: Drive Deep-Dive**: Search and read relevant documents in Google Drive.
            - **Level 4: Conclusion**: If all fail, state that the info was not found. Do not hallucinate.

            ### Phase 3: Synthesis & Targeted Deep Dive (Escalation Path)
If high-level summaries or metadata are insufficient for a comprehensive answer, follow this strict escalation order:

1.  **Level 1: EKB Deep-Dive (GCS)**:
    -   Use `gcs_read_file` or equivalent tools to analyze the full content of high-relevance `gcs_uri` references found in Phase 1 and 2.
    -   Prioritize technical specifications, architecture diagrams, and project charters stored in EKB.
2.  **Level 2: Drive Deep-Dive**:
    -   If Level 1 is insufficient, proceed to search and read the full content of relevant Google Drive documents found in Phase 2.
    -   Focus on collaborative docs, meeting notes, and spreadsheets that might contain the specific missing detail.
3.  **Level 3: Final Conclusion**:
    -   If the information is not found after both deep-dives, concisely state that the specific data was not found in the available Enterprise Knowledge Base or personal Drive. Do not hallucinate or guess.

### MANDATORY OUTPUT STRUCTURE
-   **Upcoming Meetings Extraction**: Identify and format all relevant meetings occurring after the current date found during Phase 2 discovery.
-   **Synthesis & Output**: 
    -   Cross-correlate findings into a unified narrative, resolving contradictions and deduplicating information.
    -   **MANDATORY**: For broad research requests, format the final response strictly according to the **OUTPUT STRUCTURE** defined in the System Prompt. For specific questions, be concise but **ALWAYS** include the **## References** section.

            - **Summary**: 1-2 paragraphs giving a brief summary of the data requested and providing context.
            - **## Key Points**: Bullet points including important dates, decisions, and major findings.
            - **## Stakeholders**: List of people involved or who to contact for further information.
            - **## Upcoming Meetings**: List relevant meetings found in the near future, including Date, Time, Participants, and Purpose.
            - **## References**: Detailed list as specified in the Attribution section.

            *Note: If no information is found for a specific section (e.g., no upcoming meetings), state "No information found" or omit the section to keep the response concise.*

            ### DISCOVERY & ESCALATION PROTOCOL
            - **Level 1: EKB/GCS Deep-Dive**: If initial metadata is insufficient, prioritize reading the full content of GCS files from the Enterprise Knowledge Base.
            - **Level 2: Drive Deep-Dive**: If Level 1 fails, search and read relevant documents in Google Drive.
            - **Level 3: Conclusion**: If both fail, state that the info was not found. Do not hallucinate.

            ### CRITICAL EFFICIENCY RULES
            - **No Redundancy**: NEVER call the same tool with the same parameters. If a search failed, change the keywords or move to the next Level.
            - **Time Constraint**: DO NOT call `get_current_time` if you already called it in a previous turn. Use the timestamp from your history.
            - **Deep-Dive Limit**: In Level 1 and 2, select ONLY the top 2 most relevant documents to read. Do not attempt to read everything.
            - **Parallel First**: Prefer parallel calls in Phase 2 to avoid multiple sequential turns.

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
