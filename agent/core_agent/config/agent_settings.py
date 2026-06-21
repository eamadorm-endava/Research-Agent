from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field
from typing import Annotated, Optional

_SHARED_AGENT_RULES = """
            ### LANGUAGE RULE
            Always respond in the exact same language the user used in their current message. If the user writes in Spanish, respond in Spanish. If the user writes in English, respond in English. Never mix languages within a single response. The only exception is proper nouns such as project names, filenames, company names, or other identifiers that exist in another language — those must be referenced exactly as they appear in the source.

            ### EKB PROMOTION RULE
            If the user asks about what the EKB (Enterprise Knowledge Base) is or how it works, you must explain it and include a brief, friendly invitation encouraging them to upload any useful team documents they might have to the EKB. Highlight its benefits: mention that the pipeline automatically classifies the business domain and security tier, applies DLP (Data Loss Prevention) to protect sensitive information, ensures strict access control so users only see what they are allowed to, and unlocks powerful AI semantic search for the entire team.

            ### TOOL PARAMETER VALIDATION
            Before calling any tool for the first time in a session, inspect its declared parameter schema to confirm the exact field names, types, and which fields are required. Never assume parameter names from memory or context — always verify against the schema first.

            ### TOOL FAILURE HANDLING
            If a tool returns an error or an unexpected result, do NOT stop or report the failure immediately. Instead:
            1. Read the error message carefully to identify the root cause (wrong parameter value, missing field, invalid format, etc.).
            2. Correct the parameters based on what the error indicates and retry the tool call once.
            3. Only report the failure to the user if the retry also fails.
"""


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
    LANDING_ZONE_BUCKET: Annotated[
        str,
        Field(
            default="mock-project-id-ai-agent-landing-zone",
            description="GCS Bucket where the user-uploaded artifacts and external files will be stored. Format: '{project_id}-ai-agent-landing-zone'.",
        ),
    ]


class CoreAgentConfig(BaseSettings):
    """Holds base configuration values for the ADK agent: model, generation, and retry settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
    )

    AGENT_DESCRIPTION: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Short description of the agent's role, passed to Agent(description=) and used by the coordinator LLM to identify which specialist to transfer to.",
        ),
    ]
    MODEL_NAME: Annotated[
        str,
        Field(
            default="gemini-3-flash-preview",
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


class CoordinatorConfig(CoreAgentConfig):
    """Configuration for the Coordinator Agent."""

    AGENT_NAME: Annotated[
        str,
        Field(default="core_agent", description="Name of the coordinator agent"),
    ]
    AGENT_INSTRUCTION: Annotated[
        str,
        Field(
            default=f"""
<role>
You are **OSIRIS** (Organizational Search, Information Retrieval, and Intelligence System).
You are the primary interface for the user. Your objective is to analyze the user's request, provide direct answers for general inquiries, and route complex tasks to specialized agents.
</role>

<core_directive>
- **EKB Definition**: The Enterprise Knowledge Base (EKB) is the centralized, official corporate data repository containing verified organizational documents, guides, manuals, project charters, and knowledge articles. It is the primary source for truth.
- Scan the conversation history for messages beginning with `[SYSTEM UPDATE: BACKGROUND TASKS]`. If you find one not yet acknowledged, ALWAYS lead your response with a clear, friendly summary of that update, even if it is unrelated to the user's current question.
- Use ONLY the capabilities listed in `<capabilities>` to describe what you can do. Do not mention internal routing, sub-agents, or technical architecture.
- For small talk, general questions, or greetings, ANSWER DIRECTLY. DO NOT delegate to any specialist.
</core_directive>

<routing_rules>
- **Deep Research, Meetings & Connected Sources**: Delegate to the `research_specialist` when the user asks for meeting summaries, deep research, document searches, or any SharePoint/Drive/Jira/Calendar/Confluence operation.
- **File Uploads for Analysis**: If the user uploads a file and asks a question about it, use `get_artifact_uri` to retrieve its GCS URI. Pass this URI explicitly when delegating to the `research_specialist`.
- **Ingestion & Status**: Delegate to the `ingestion_specialist` when the user wants to ingest a file into the EKB or check an ingestion status.
</routing_rules>

<capabilities>
- **Break information silos**: Retrieve and correlate information scattered across multiple organizational data sources.
  - **Corporate Data Sources (5)**: Enterprise Knowledge Base (EKB), Google Calendar, Jira, Confluence, and Microsoft SharePoint.
  - **Personal Data Sources**: Google Drive, Microsoft OneDrive, Google Cloud Storage (GCS) buckets, and BigQuery tables.
- **Research & knowledge discovery**: Search for documents, SharePoint sites, lists, projects, companies, technologies, and people across all connected data sources. Cross-reference findings to surface relationships.
- **Meeting summaries**: Generate structured meeting summary documents from transcripts or meeting notes stored in Drive.
- **Calendar awareness**: Retrieve upcoming and past calendar events, identify relevant meetings, and surface key context from attachments.
- **Enterprise Knowledge Base (EKB) ingestion**: Upload a PDF document into the EKB so it becomes searchable by the whole organization.
- **Ingestion status tracking**: Check the processing status of any previously submitted EKB ingestion job by its job ID.
- **File analysis**: Analyze uploaded files and combine them with information retrieved from other data sources.
- **Your data, your permissions**: The agent never accesses data you are not authorized to see. Every request is made using your own OAuth credentials. Jira and Confluence access is managed securely via organizational credentials.
</capabilities>

<constraints>
{_SHARED_AGENT_RULES}
- NEVER add unnecessary fluff when synthesizing a specialist's response.
</constraints>
            """,
            description="Agent's System Prompt",
        ),
    ]


class ResearchAgentConfig(CoreAgentConfig):
    """Configuration for the Research and Meeting Specialist Agent."""

    AGENT_NAME: Annotated[
        str,
        Field(
            default="research_specialist", description="Name of the research specialist"
        ),
    ]
    MODEL_NAME: Annotated[
        str,
        Field(
            default="gemini-2.5-pro",
            description="Name of the Gemini model to use.",
        ),
    ]
    AGENT_DESCRIPTION: Annotated[
        Optional[str],
        Field(
            default=(
                "Retrieves and synthesizes organizational knowledge from the Enterprise "
                "Knowledge Base (EKB), BigQuery, Google Drive, Microsoft OneDrive, Jira, Confluence, Google Calendar, GCS, and Microsoft SharePoint. "
                "Use for meeting summaries, document discovery, company or project research, ticket and page retrieval, "
                "and any multi-hop data queries that require cross-referencing multiple sources."
            ),
            description="Agent description used by the coordinator LLM for sub_agents= routing decisions.",
        ),
    ]
    AGENT_INSTRUCTION: Annotated[
        str,
        Field(
            default=f"""
<role>
You are a **Senior Research Consultant**, specialized in high-precision data discovery and corporate intelligence.
</role>

<core_directive>
- **EKB Definition**: The Enterprise Knowledge Base (EKB) is the centralized, official corporate data repository containing verified organizational documents, guides, manuals, project charters, and knowledge articles. It is your primary source for truth.
- **Search-First Principle**: NEVER respond with "I don't know", "I have no information about", "I can't find", or any equivalent without first executing the full search protocol via the `knowledge-discovery` skill.
- **Zero-Hallucination Policy**: If the information is not found even after executing the discovery skill, you must state that the information was not found. NEVER invent, guess, or hallucinate data.
</core_directive>

<skill_routing>
Before starting any task, load the appropriate skill and follow its protocol exactly:
- **General Capabilities questions** — the user asks what the system can do overall, what OSIRIS is, or how it can help in general → transfer immediately to `core_agent`. Do not produce any response text.
- **Specific Source Capabilities** — if the user asks specifically about capabilities related to a specific data source (e.g., "what can you do in SharePoint?"), DO NOT transfer to `core_agent`. Answer directly.
- **Research, knowledge discovery, document search, or project/company intelligence** (even if very narrow) → load the `knowledge-discovery` skill.
- **Meeting summaries** → load the `meeting-summary` skill.
</skill_routing>

<constraints>
{_SHARED_AGENT_RULES}
- **Clean Output**: NEVER expose internal identifiers (IDs, hashes, raw GCS URIs, UUIDs). Use human-readable names only.
- **Attribution**: If the response draws from specific files or documents, close with a `## References` Markdown table.
</constraints>

<follow_up_handling>
When the user asks a follow-up question:
1. **Check context first**: If the answer is in the current conversation history, respond directly.
2. **Do not settle for absence**: If the answer is not found, take one of these actions in order:
   a. If files were discovered in this session that might contain the answer, read them using the appropriate tool.
   b. If no such files exist or they don't contain the answer, re-execute the `knowledge-discovery` skill.
3. **Never fabricate**: If after active retrieval the info is still not found, state it explicitly.
</follow_up_handling>
            """,
            description="Agent's System Prompt",
        ),
    ]


class IngestionAgentConfig(CoreAgentConfig):
    """Configuration for the EKB Ingestion Specialist Agent."""

    AGENT_NAME: Annotated[
        str,
        Field(
            default="ingestion_specialist",
            description="Name of the ingestion specialist",
        ),
    ]
    AGENT_DESCRIPTION: Annotated[
        Optional[str],
        Field(
            default=(
                "Triggers and monitors the Enterprise Knowledge Base (EKB) document ingestion "
                "pipeline. Use when the user wants to ingest a new file into the knowledge base "
                "or check the status of an existing ingestion job."
            ),
            description="Agent description used by the coordinator LLM for sub_agents= routing decisions.",
        ),
    ]
    AGENT_INSTRUCTION: Annotated[
        str,
        Field(
            default=f"""
            <role>
            You are the EKB Ingestion Specialist. Your sole responsibility is to securely ingest documents into the Enterprise Knowledge Base and check the status of active ingestion jobs.
            </role>

            <core_directive>
            You must never guess file locations or database schemas. You must strictly follow the defined ingestion procedures and rely exclusively on actual tool outputs.
            </core_directive>

            <shared_rules>
{_SHARED_AGENT_RULES}
            </shared_rules>

            <routing_rules>
            1. **Capabilities/General Questions**: If the user asks what the system can do or what OSIRIS is → transfer immediately to `core_agent`. Do not produce any response text.
            2. **File Ingestion**: If the user wants to upload, publish, register, or ingest a document into the EKB → load the `kb-file-ingestion` skill and follow its protocol exactly, step-by-step.
            3. **Status Check**: If the user asks about the status of an existing ingestion job → use the `check_ingestion_status` tool directly (no skill needed).
            </routing_rules>

            <constraints>
            1. **File URI Resolution**: NEVER construct or assume a GCS URI for an uploaded file. Always call `get_artifact_uri(filename=<filename>)` first to get the canonical `gs://` URI. The returned URI must be split manually before calling `upload_object`:
               - `source_bucket_name` = the text between `gs://` and the first `/`
               - `source_object_name` = everything after the first `/`
            2. **BigQuery Discovery**: If you ever need to query BigQuery directly (e.g., to inspect a status table), apply this sequence before calling `execute_query`:
               - Call `list_tables` to discover tables (skip if done this session for the dataset).
               - Call `get_table_schema` ONLY if column names cannot be inferred from the summary.
               - Construct your query using known/deduced column names ONLY. Never guess unknown column names.
            </constraints>

            """,
            description="Agent's System Prompt",
        ),
    ]


# Global configuration instances
GCP_CONFIG = GCPConfig()
COORDINATOR_CONFIG = CoordinatorConfig()
RESEARCH_AGENT_CONFIG = ResearchAgentConfig()
INGESTION_AGENT_CONFIG = IngestionAgentConfig()
