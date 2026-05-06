from google.adk.agents.context import Context
from google.adk.tools import load_artifacts

from .builder import AgentBuilder, AppBuilder
from .config import (
    GCP_CONFIG,
    AGENT_CONFIG,
    BIGQUERY_MCP_CONFIG,
    CALENDAR_MCP_CONFIG,
    DRIVE_MCP_CONFIG,
    GCS_MCP_CONFIG,
    GOOGLE_AUTH_CONFIG,
)

from .tools.artifact_tools import (
    GetArtifactUriTool,
    ImportGcsToArtifactTool,
)
from .tools.kb_tools import TriggerEKBPipelineTool, CheckIngestionStatusTool
from .tools.time_tools import GetCurrentTimeTool
from .callbacks.ingestion_status import sync_ingestion_status
from loguru import logger

mcp_servers_to_mount = [
    BIGQUERY_MCP_CONFIG,
    DRIVE_MCP_CONFIG,
    CALENDAR_MCP_CONFIG,
    GCS_MCP_CONFIG,
]

skills_to_mount = [
    "meeting-summary",
    "kb-file-ingestion",
    "knowledge-discovery",
]


async def log_agent_output(callback_context: Context):
    """
    Debug callback to print the final agent response to the terminal.
    """
    if callback_context.session.events:
        # Inspeccionamos los últimos eventos para entender qué está pasando
        events_to_show = callback_context.session.events[-3:]
        logger.debug(f"[DEBUG] Inspecting last {len(events_to_show)} events:")

        for i, event in enumerate(events_to_show):
            part_types = []
            if event.content and event.content.parts:
                for p in event.content.parts:
                    if p.text:
                        part_types.append(f"text({len(p.text)})")
                    if p.function_call:
                        part_types.append(f"call({p.function_call.name})")
                    if p.function_response:
                        part_types.append(f"resp({p.function_response.name})")
                    if p.thought:
                        part_types.append("thought")

            logger.debug(
                f"  Event[-{len(events_to_show) - i}]: author={event.author}, parts=[{', '.join(part_types)}]"
            )

        # Intentamos mostrar el texto del último evento del agente
        last_agent_event = next(
            (
                e
                for e in reversed(callback_context.session.events)
                if e.author == callback_context.agent_name and e.content
            ),
            None,
        )
        if last_agent_event:
            text_parts = [p.text for p in last_agent_event.content.parts if p.text]
            if text_parts:
                full_text = "".join(text_parts)
                logger.info(
                    f"[DEBUG] Final Agent Response (len={len(full_text)}):\n{full_text[:500]}..."
                )
            else:
                logger.debug("Last agent event has content but NO text parts.")


root_agent = (
    AgentBuilder(
        agent_config=AGENT_CONFIG,
        gcp_config=GCP_CONFIG,
        auth_config=GOOGLE_AUTH_CONFIG,
    )
    .with_skills(skills_to_mount)
    .with_mcp_servers(mcp_servers_to_mount)
    .with_before_agent_callback(sync_ingestion_status)
    .with_after_agent_callback(log_agent_output)
    .with_native_tools(
        [
            GetArtifactUriTool(),
            ImportGcsToArtifactTool(),
            TriggerEKBPipelineTool(),
            CheckIngestionStatusTool(),
            GetCurrentTimeTool(),
            load_artifacts,
        ]
    )
    .build()
)

app = AppBuilder(
    agent=root_agent,
    gcp_config=GCP_CONFIG,
    agent_config=AGENT_CONFIG,
).build()

logger.info("ADK Agent application initialized and ready for execution.")
