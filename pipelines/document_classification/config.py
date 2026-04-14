from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Annotated


class EKBConfig(BaseSettings):
    """Configuration class for the Enterprise Knowledge Base (EKB) pipeline.

    This class manages environment variables and technical constants for the
    document classification and metadata extraction process.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_ID: Annotated[
        str,
        Field(
            default="your-project-id",
            description="GCP Project ID to use for DLP and BigQuery.",
        ),
    ]
    LOCATION: Annotated[
        str,
        Field(
            default="us-central1", description="GCP Location for regional processing."
        ),
    ]

    # GCS Settings
    LANDING_ZONE_BUCKET: Annotated[
        str,
        Field(
            default="knowledge_base_landing_zone",
            description="GCS bucket where documents are initially uploaded.",
        ),
    ]

    # BigQuery Settings
    BQ_DATASET: Annotated[
        str,
        Field(
            default="knowledge_base",
            description="BigQuery dataset for metadata storage.",
        ),
    ]
    BQ_TABLE: Annotated[
        str,
        Field(
            default="documents_metadata",
            description="BigQuery table for document metadata.",
        ),
    ]

    # DLP Patterns
    TIER_5_INFOTYPES: list[str] = [
        "US_SOCIAL_SECURITY_NUMBER",
        "CREDIT_CARD_NUMBER",
        "IBAN_CODE",
        "SWIFT_CODE",
        "GCP_API_KEY",
        "JSON_WEB_TOKEN",
        "PASSPORT",
    ]

    TIER_4_KEYWORDS: list[str] = [
        "Confidential",
        "Proprietary",
        "Internal Strategy",
        "Strictly Private",
    ]

    # Domain list
    DOMAINS: list[str] = [
        "it",
        "finance",
        "hr",
        "sales",
        "executives",
        "legal",
        "operations",
    ]


EKB_CONFIG = EKBConfig()
