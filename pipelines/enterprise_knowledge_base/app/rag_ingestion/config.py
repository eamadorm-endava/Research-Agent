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

    RAG_STAGING_BUCKET: Annotated[
        str,
        Field(
            default="mock-rag-staging-bucket",
            description="Dedicated GCS bucket for RAG ingestion staging lifecycle.",
        ),
    ]

    BQ_CHUNKS_TABLE: Annotated[
        str,
        Field(
            default="mock-chunks-table",
            description="The BigQuery table for storing document chunks.",
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

    GCS_MAX_RETRIES: Annotated[
        int,
        Field(
            default=3,
            description="Maximum number of retry attempts for GCS operations.",
        ),
    ]

    GCS_BASE_DELAY: Annotated[
        int,
        Field(
            default=2,
            description="Base delay in seconds for exponential backoff calculation.",
        ),
    ]


RAG_CONFIG = RAGConfig()
