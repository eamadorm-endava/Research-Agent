from typing import Annotated
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


EKB_TOOLS_CONFIG = EKBToolsConfig()
