from typing import Annotated
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MetricsConfig(BaseSettings):
    """Configuration for the Metrics Plugin."""

    project_id: Annotated[
        str, Field(description="GCP Project ID", default="ag-core-ops-auj0")
    ]
    dataset_id: Annotated[
        str, Field(description="BigQuery Dataset ID", default="agent_metrics")
    ]
    table_id: Annotated[
        str, Field(description="BigQuery Table ID", default="response_times")
    ]

    model_config = SettingsConfigDict(env_prefix="METRICS_")


METRICS_CONFIG = MetricsConfig()
