from google.adk.tools import load_artifacts

from .builder import AgentBuilder, AppBuilder
from .tools.artifact_tools import GetArtifactURITool
from .tools.ekb_tools import TriggerEKBPipelineTool, CheckIngestionStatusTool
from .tools.time_tools import GetCurrentTimeTool
from .callbacks.before_agent_callbacks import sync_ekb_job_status
from loguru import logger
from .plugins.gemini_enterprise_ingestion import GeminiEnterpriseFileIngestionPlugin
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin
from .plugins.multimodal_file_injection import MultimodalFileInjectionPlugin
from .plugins.continuation import ContinuationPlugin
from .plugins.observability_plugin.plugin import ObservabilityPlugin
from .config import (
    GCP_CONFIG,
    COORDINATOR_CONFIG,
    RESEARCH_AGENT_CONFIG,
    INGESTION_AGENT_CONFIG,
    BigQueryMCPConfig,
    CalendarMCPConfig,
    DriveMCPConfig,
    GCSMCPConfig,
    OneDriveMCPConfig,
    SharePointMCPConfig,
    AtlassianMCPConfig,
    OutlookMCPConfig,
    GOOGLE_AUTH_CONFIG,
    MICROSOFT_AUTH_CONFIG,
    ATLASSIAN_AUTH_CONFIG,
)
import os
import uuid
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.cloud_monitoring import CloudMonitoringMetricsExporter
from opentelemetry.sdk.resources import Resource


def init_gcp_metrics():
    # Evita la doble inicialización si el worker se recarga
    if isinstance(metrics.get_meter_provider(), MeterProvider):
        return

    try:
        exporter = CloudMonitoringMetricsExporter()

        # 15 segundos evita el límite de GCP (10s) y le gana al CPU Throttling
        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=15000)

        # Crea un identificador inmutable y único para cada proceso de Python (worker)
        worker_id = f"worker-{os.getpid()}-{uuid.uuid4().hex[:8]}"

        # El atributo service.instance.id es el estándar de OpenTelemetry para aislar réplicas
        resource = Resource.create(
            {"service.name": "osiris-agent", "service.instance.id": worker_id}
        )

        # Asigna el provider con el recurso etiquetado
        provider = MeterProvider(metric_readers=[reader], resource=resource)
        metrics.set_meter_provider(provider)

        print(f"Exportador OTel inicializado correctamente para {worker_id}")
    except Exception as e:
        print(f"Advertencia: Fallo al inicializar métricas de GCP: {e}")


# Llama a la función inmediatamente en la carga del módulo
init_gcp_metrics()


# Llama a la función ANTES de instanciar tu app
init_gcp_metrics()


# ---------------------------------------------------------------------------
# MCP Configuration Instantiation
# ---------------------------------------------------------------------------
BIGQUERY_MCP_CONFIG = BigQueryMCPConfig(OAUTH_CONFIG=GOOGLE_AUTH_CONFIG)
DRIVE_MCP_CONFIG = DriveMCPConfig(OAUTH_CONFIG=GOOGLE_AUTH_CONFIG)
CALENDAR_MCP_CONFIG = CalendarMCPConfig(OAUTH_CONFIG=GOOGLE_AUTH_CONFIG)
GCS_MCP_CONFIG = GCSMCPConfig(OAUTH_CONFIG=GOOGLE_AUTH_CONFIG)
ONEDRIVE_MCP_CONFIG = OneDriveMCPConfig(OAUTH_CONFIG=MICROSOFT_AUTH_CONFIG)
SHAREPOINT_MCP_CONFIG = SharePointMCPConfig(OAUTH_CONFIG=MICROSOFT_AUTH_CONFIG)
ATLASSIAN_MCP_CONFIG = AtlassianMCPConfig(OAUTH_CONFIG=ATLASSIAN_AUTH_CONFIG)
OUTLOOK_MCP_CONFIG = OutlookMCPConfig(OAUTH_CONFIG=MICROSOFT_AUTH_CONFIG)


# ---------------------------------------------------------------------------
# 1. Research & Meetings Specialist
# ---------------------------------------------------------------------------
research_agent = (
    AgentBuilder(
        agent_config=RESEARCH_AGENT_CONFIG,
        gcp_config=GCP_CONFIG,
    )
    .with_skills(["meeting-summary", "knowledge-discovery"])
    .with_mcp_servers(
        [
            BIGQUERY_MCP_CONFIG,
            DRIVE_MCP_CONFIG,
            CALENDAR_MCP_CONFIG,
            GCS_MCP_CONFIG,
            ATLASSIAN_MCP_CONFIG,
            ONEDRIVE_MCP_CONFIG,
            SHAREPOINT_MCP_CONFIG,
            OUTLOOK_MCP_CONFIG,
        ]
    )
    .with_native_tools(
        [
            GetArtifactURITool(),
            GetCurrentTimeTool(),
            load_artifacts,
        ]
    )
    .with_before_agent_callback([sync_ekb_job_status])
    .with_output_key("research_context")
    .build()
)

# ---------------------------------------------------------------------------
# 2. Ingestion Specialist
# ---------------------------------------------------------------------------
ingestion_agent = (
    AgentBuilder(
        agent_config=INGESTION_AGENT_CONFIG,
        gcp_config=GCP_CONFIG,
    )
    .with_skills(["kb-file-ingestion"])
    .with_mcp_servers(
        [
            BIGQUERY_MCP_CONFIG,
            GCS_MCP_CONFIG,
        ]
    )
    .with_native_tools(
        [
            GetArtifactURITool(),
            GetCurrentTimeTool(),
            TriggerEKBPipelineTool(),
            CheckIngestionStatusTool(),
            load_artifacts,
        ]
    )
    .with_before_agent_callback([sync_ekb_job_status])
    .with_output_key("ekb_ingestion_context")
    .build()
)

# ---------------------------------------------------------------------------
# 3. Coordinator (Root Agent)
# ---------------------------------------------------------------------------
root_agent = (
    AgentBuilder(
        agent_config=COORDINATOR_CONFIG,
        gcp_config=GCP_CONFIG,
    )
    .with_subagents([research_agent, ingestion_agent])
    .with_before_agent_callback([sync_ekb_job_status])
    .with_native_tools([GetArtifactURITool(), GetCurrentTimeTool(), load_artifacts])
    .build()
)

app = (
    AppBuilder(
        agent=root_agent,
        gcp_config=GCP_CONFIG,
        agent_config=COORDINATOR_CONFIG,
    )
    .with_plugins(
        (
            # SaveFilesAsArtifactsPlugin targets ADK Web UI only; in production,
            # GeminiEnterpriseFileIngestionPlugin handles upload persistence instead.
            [
                GeminiEnterpriseFileIngestionPlugin(),
                MultimodalFileInjectionPlugin(),
                ContinuationPlugin(),
                ObservabilityPlugin(),
            ]
            if GCP_CONFIG.PROD_EXECUTION
            else [
                SaveFilesAsArtifactsPlugin(),
                MultimodalFileInjectionPlugin(),
                ContinuationPlugin(),
                ObservabilityPlugin(),
            ]
        )
    )
    .build()
)

logger.info("ADK Multi-Agent application initialized and ready for execution.")
