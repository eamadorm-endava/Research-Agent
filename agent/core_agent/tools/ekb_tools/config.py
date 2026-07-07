from typing import Annotated, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class EKBToolsConfig(BaseSettings):
    """Configuration for EKB tools."""

    SESSION_STATE_PENDING_JOBS_KEY: Annotated[
        str,
        Field(
            default="session_state_pending_jobs",
            description="The ADK state key used to persist the list of pending ingestion jobs",
        ),
    ]
    MAX_KEEPALIVE_CONNECTIONS: Annotated[
        int,
        Field(default=50, description="Max keepalive connections for httpx client"),
    ]
    MAX_CONNECTIONS: Annotated[
        int,
        Field(default=100, description="Max total connections for httpx client"),
    ]
    EKB_PIPELINE_URL: Annotated[
        str,
        Field(
            default="mock-pipeline-url", description="URL of the EKB pipeline service"
        ),
    ]
    PROJECT_ID: Annotated[
        str,
        Field(
            default="dummy-gcp-project-id",
            description="GCP project used to derive the default KB landing-zone bucket.",
        ),
    ]
    KB_LANDING_ZONE_BUCKET: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional explicit KB landing-zone bucket. Defaults to '<PROJECT_ID>-kb-landing-zone'.",
        ),
    ]
    MAX_SUBMIT_BATCH_CONCURRENCY: Annotated[
        int,
        Field(
            default=10,
            description="Maximum concurrent file submissions for the unified KB ingestion tool.",
        ),
    ]

    @property
    def effective_kb_landing_zone_bucket(self) -> str:
        """Returns the configured or project-derived KB landing-zone bucket."""
        if self.KB_LANDING_ZONE_BUCKET:
            return self.KB_LANDING_ZONE_BUCKET
        return f"{self.PROJECT_ID}-kb-landing-zone"


EKB_TOOLS_CONFIG = EKBToolsConfig()
