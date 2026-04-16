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

    TIER_5_INFOTYPES: list[str] = [
        "CREDIT_CARD_DATA",
        "PASSPORT",
        "SECURITY_DATA",
        "SWIFT_CODE",
    ]

    TIER_5_DOCUMENT_TYPES: list[str] = [
        "DOCUMENT_TYPE/MEDICAL/RECORD",
        "DOCUMENT_TYPE/HR/RESUME",
        "DOCUMENT_TYPE/R&D/DATABASE_BACKUP",
        "DOCUMENT_TYPE/R&D/SOURCE_CODE",
        "DOCUMENT_TYPE/R&D/SYSTEM_LOG",
    ]

    TIER_5_KEYWORDS: list[str] = [
        "Performance Improvement Plan",
        "PIP",
        "Termination Agreement",
        "Severance",
        "Due Diligence",
        "Acquisition Target",
        "Merger Agreement",
    ]

    TIER_4_INFOTYPES: list[str] = [
        "DATE",
    ]

    TIER_4_DOCUMENT_TYPES: list[str] = [
        "DOCUMENT_TYPE/FINANCE/INVOICE",
        "DOCUMENT_TYPE/FINANCE/REGULATORY",
        "DOCUMENT_TYPE/FINANCE/SEC_FILING",
        "DOCUMENT_TYPE/LEGAL/COURT_ORDER",
        "DOCUMENT_TYPE/LEGAL/BRIEF",
        "DOCUMENT_TYPE/LEGAL/BLANK_FORM",
        "DOCUMENT_TYPE/LEGAL/LAW",
        "DOCUMENT_TYPE/LEGAL/PLEADING",
    ]

    TIER_4_KEYWORDS: list[str] = [
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
    ]

    CONTEXTUAL_INFOTYPES: list[str] = [
        "GOVERNMENT_ID",
        "FINANCIAL_ID",
        "GEOGRAPHIC_DATA",
        "DEMOGRAPHIC_DATA",
        "PERSON_NAME",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "MEDICAL_ID",
    ]


EKB_CONFIG = EKBConfig()
