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

    TIER_5_INFOTYPES: Annotated[
        list[str],
        Field(
            default=[
                "CREDIT_CARD_DATA",
                "PASSPORT",
                "SECURITY_DATA",
                "SWIFT_CODE",
                "GOVERNMENT_ID",
                "FINANCIAL_ID",
                "MEDICAL_ID",
            ],
            description="Highly sensitive built-in InfoTypes triggering Tier 5 classification.",
        ),
    ]

    TIER_5_DOCUMENT_TYPES: Annotated[
        list[str],
        Field(
            default=[
                "DOCUMENT_TYPE/MEDICAL/RECORD",
                "DOCUMENT_TYPE/HR/RESUME",
                "DOCUMENT_TYPE/R&D/DATABASE_BACKUP",
                "DOCUMENT_TYPE/R&D/SOURCE_CODE",
                "DOCUMENT_TYPE/R&D/SYSTEM_LOG",
            ],
            description="Cloud DLP Document Detectors triggering Tier 5 classification.",
        ),
    ]

    TIER_5_KEYWORDS: Annotated[
        list[str],
        Field(
            default=[
                "Performance Improvement Plan",
                "PIP",
                "Termination Agreement",
                "Severance",
                "Due Diligence",
                "Acquisition Target",
                "Merger Agreement",
            ],
            description="Custom keywords triggering Tier 5 classification.",
        ),
    ]

    TIER_4_INFOTYPES: Annotated[
        list[str],
        Field(
            default=[],
            description="Medium-sensitivity built-in InfoTypes triggering Tier 4 classification.",
        ),
    ]

    TIER_4_DOCUMENT_TYPES: Annotated[
        list[str],
        Field(
            default=[
                "DOCUMENT_TYPE/FINANCE/INVOICE",
                "DOCUMENT_TYPE/FINANCE/REGULATORY",
                "DOCUMENT_TYPE/FINANCE/SEC_FILING",
                "DOCUMENT_TYPE/LEGAL/COURT_ORDER",
                "DOCUMENT_TYPE/LEGAL/BRIEF",
                "DOCUMENT_TYPE/LEGAL/BLANK_FORM",
                "DOCUMENT_TYPE/LEGAL/LAW",
                "DOCUMENT_TYPE/LEGAL/PLEADING",
            ],
            description="Cloud DLP Document Detectors triggering Tier 4 classification.",
        ),
    ]

    TIER_4_KEYWORDS: Annotated[
        list[str],
        Field(
            default=[
                "Confidential",
                "Proprietary",
                "Under NDA",
                "Roadmap",
                "OKR",
                "EBITDA",
                "Q1 Target",
                "Q2 Target",
                "Q3 Target",
                "Q4 Target",
            ],
            description="Custom keywords triggering Tier 4 classification.",
        ),
    ]

    CONTEXTUAL_INFOTYPES: Annotated[
        list[str],
        Field(
            default=[
                "GEOGRAPHIC_DATA",
                "DEMOGRAPHIC_DATA",
                "PERSON_NAME",
                "EMAIL_ADDRESS",
                "PHONE_NUMBER",
                "DATE",
            ],
            description="General PII that requires masking only when high-risk context is detected.",
        ),
    ]


EKB_CONFIG = EKBConfig()
