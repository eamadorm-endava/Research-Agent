from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Annotated


class EKBConfig(BaseSettings):
    """Global configuration for the Enterprise Knowledge Base (EKB) pipeline.

    This class manages global environment variables and constants used across
    the entire pipeline, including Cloud Tasks and BigQuery tracking.
    """

    model_config = SettingsConfigDict(
        env_file=[".env", "../../.env", "../../../.env", "../../../../.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_ID: Annotated[
        str,
        Field(
            default="mock-project-id",
            description="GCP Project ID to use for DLP and BigQuery.",
        ),
    ]

    BQ_DATASET: Annotated[
        str,
        Field(
            default="mock-dataset",
            description="The BigQuery dataset for metadata storage.",
        ),
    ]

    BQ_METADATA_TABLE: Annotated[
        str,
        Field(
            default="mock-metadata-table",
            description="The BigQuery table for metadata storage.",
        ),
    ]

    BQ_JOBS_TABLE: Annotated[
        str,
        Field(
            default="ingestion_jobs",
            description="The BigQuery table for tracking async job status.",
        ),
    ]


EKB_CONFIG = EKBConfig()
