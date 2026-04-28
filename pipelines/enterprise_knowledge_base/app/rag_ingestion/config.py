from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Annotated


class RAGConfig(BaseSettings):
    """Configuration class for the RAG Ingestion Service.

    Manages environment variables and technical constants for the
    PDF parsing, chunking, and BigQuery staging process.
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
            description="GCP Project ID to use for BigQuery and GCS.",
        ),
    ]

    RAG_STAGING_BUCKET: Annotated[
        str,
        Field(
            default="mock-rag-staging-bucket",
            description="Dedicated GCS bucket for RAG ingestion staging lifecycle.",
        ),
    ]

    BQ_DATASET: Annotated[
        str,
        Field(
            default="mock-dataset",
            description="The BigQuery dataset for storing document chunks.",
        ),
    ]

    BQ_CHUNKS_TABLE: Annotated[
        str,
        Field(
            default="mock-chunks-table",
            description="The BigQuery table for storing document chunks.",
        ),
    ]

    BQ_METADATA_TABLE: Annotated[
        str,
        Field(
            default="mock-metadata-table",
            description="The BigQuery table for joining with metadata.",
        ),
    ]

    CHUNK_SIZE: Annotated[
        int,
        Field(
            default=1000,
            description="Maximum number of characters per chunk.",
        ),
    ]

    CHUNK_OVERLAP: Annotated[
        int,
        Field(
            default=100,
            description="Number of overlapping characters between chunks.",
        ),
    ]

    GCS_INGESTED_PREFIX: Annotated[
        str,
        Field(
            default="ingested/",
            description="Prefix for source documents to be processed.",
        ),
    ]

    GCS_PROCESSED_PREFIX: Annotated[
        str,
        Field(
            default="processed/",
            description="Prefix for successfully processed documents.",
        ),
    ]


RAG_CONFIG = RAGConfig()
