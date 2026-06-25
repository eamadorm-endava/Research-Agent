from typing import Annotated
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MetricsConfig(BaseSettings):
    """Configuration for the Metrics Plugin."""

    model_config = SettingsConfigDict(
        env_prefix="METRICS_",
        env_file="core_agent/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_ID: Annotated[
        str, Field(description="GCP Project ID", default="mock-project-id")
    ]
    DATASET_ID: Annotated[
        str, Field(description="BigQuery Dataset ID", default="mock-dataset-id")
    ]
    TABLE_ID: Annotated[
        str, Field(description="BigQuery Table ID", default="mock-table-id")
    ]


METRICS_CONFIG = MetricsConfig()
