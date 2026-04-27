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
                "US_SOCIAL_SECURITY_NUMBER",
                "CREDIT_CARD_NUMBER",
                "PASSPORT",
                "GCP_API_KEY",
                "AUTH_TOKEN",
                "IBAN_CODE",
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

    GEMINI_MODEL: Annotated[
        str,
        Field(
            default="gemini-2.5-flash",
            description="The Gemini model to use for contextual classification.",
        ),
    ]

    GEMINI_LOCATION: Annotated[
        str,
        Field(
            default="us-central1",
            description="The GCP location for the Gemini model.",
        ),
    ]

    CLASSIFICATION_MATRIX: Annotated[
        str,
        Field(
            default="""
| Tier | Label | Risk Level | Definition & Rationale |
|---|---|---|---|
| 1 | Public | None | Information approved for external release. Unauthorized disclosure causes no measurable organizational harm. |
| 2 | Internal Use Only | Low | Information intended exclusively for internal employees. Unauthorized disclosure causes limited reputational harm. |
| 3 | Client Confidential | Moderate | Information pertaining to specific named clients under contractual obligation (NDA, MSA, SOW). |
| 4 | Confidential | High | Sensitive internal strategic and proprietary information. Unauthorized disclosure could cause significant competitive harm. |
| 5 | Strictly Confidential | Critical | Need-to-know basis only. Unauthorized disclosure causes catastrophic harm (legal liability, PII, HR records). |
""",
            description="The ISO/IEC 27001:2022 and NIST aligned classification matrix for grounding.",
        ),
    ]

    VALID_DOMAINS: Annotated[
        list[str],
        Field(
            default=[
                "it",
                "finance",
                "hr",
                "sales",
                "executives",
                "legal",
                "operations",
            ],
            description="The list of valid target business domains established in the design doc.",
        ),
    ]

    BQ_DATASET: Annotated[
        str,
        Field(
            default="knowledge_base",
            description="The BigQuery dataset for metadata storage.",
        ),
    ]

    BQ_TABLE: Annotated[
        str,
        Field(
            default="documents_metadata",
            description="The BigQuery table for metadata storage.",
        ),
    ]

    TIER_TO_LABEL: Annotated[
        dict[int, str],
        Field(
            default={
                1: "public",
                2: "internal-use-only",
                3: "client-confidential",
                4: "confidential",
                5: "strictly-confidential",
            },
            description="Mapping from numeric tiers to URL-friendly string labels.",
        ),
    ]


EKB_CONFIG = EKBConfig()
