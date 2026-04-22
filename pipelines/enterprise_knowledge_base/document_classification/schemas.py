from pydantic import BaseModel, Field
from typing import Annotated, Optional, Literal


class DocumentMetadata(BaseModel):
    """Schema for document metadata extracted from GCS."""

    filename: Annotated[str, Field(description="The name of the file.")]
    mime_type: Annotated[str, Field(description="The MIME type of the content.")]
    proposed_domain: Annotated[
        Optional[str], Field(description="The detected or proposed domain.")
    ]
    trust_level: Annotated[
        Optional[str],
        Field(description="The trust maturity level (published, wip, archived)."),
    ]
    project_name: Annotated[
        Optional[str],
        Field(description="The associated project identifier.", default=None),
    ]
    uploader_email: Annotated[
        Optional[str], Field(description="The email of the uploader.", default=None)
    ]
    creator_name: Annotated[
        Optional[str],
        Field(description="The display name of the creator.", default=None),
    ]
    ingested_at: Annotated[
        Optional[str], Field(description="ISO timestamp of ingestion.", default=None)
    ]


class DLPTriggerResponse(BaseModel):
    """Schema for the response of the DLP trigger pipeline."""

    sanitized_gcs_uri: Annotated[
        str, Field(description="The URI of the sanitized/masked document.")
    ]
    proposed_classification_tier: Annotated[
        Optional[int], Field(description="The suggested classification tier (1-5).")
    ]


class ContextualClassificationResponse(BaseModel):
    """Schema for the response of the Gemini contextual classification."""

    final_classification_tier: Annotated[
        int, Field(description="The definitive security tier (1-5).", ge=1, le=5)
    ]
    confidence: Annotated[
        float,
        Field(
            description="The model's confidence in its classification (0.0 - 1.0).",
            ge=0.0,
            le=1.0,
        ),
    ]
    final_domain: Annotated[
        Literal["it", "finance", "hr", "sales", "executives", "legal", "operations"],
        Field(description="The validated target business domain."),
    ]
    file_description: Annotated[
        str, Field(description="A brief summary of the document, less than 150 words.")
    ]


class BQMetadataRecord(BaseModel):
    """Schema for a single metadata record stored in BigQuery."""

    document_id: Annotated[str, Field(description="Unique UUID for the document.")]
    gcs_uri: Annotated[
        str, Field(description="Final GCS URI in the domain bucket (Original).")
    ]
    filename: Annotated[str, Field(description="The original filename.")]
    classification_tier: Annotated[
        int, Field(description="Numeric classification tier (1-5).")
    ]
    domain: Annotated[str, Field(description="The business domain (it, hr, etc.).")]
    confidence_score: Annotated[
        float, Field(description="AI classifier confidence (0.0 - 1.0).")
    ]
    trust_level: Annotated[
        str, Field(description="Trust maturity (published, wip, archived).")
    ]
    project_id: Annotated[str, Field(description="Project identifier.")]
    uploader_email: Annotated[str, Field(description="Uploader's email address.")]
    description: Annotated[str, Field(description="AI-generated content summary.")]
    version: Annotated[int, Field(description="Incremental version number.", default=1)]
    is_latest: Annotated[bool, Field(description="Whether this is the latest version.")]
    ingested_at: Annotated[str, Field(description="ISO 8601 ingestion timestamp.")]


class FileRoutingRequest(BaseModel):
    """Request schema for the file_routing method."""

    original_landing_uri: Annotated[
        str, Field(description="Source URI in landing zone.")
    ]
    sanitized_landing_uri: Annotated[
        Optional[str], Field(description="Masked URI in landing zone (if any).")
    ]
    final_domain: Annotated[str, Field(description="Target business domain.")]
    final_security_tier: Annotated[int, Field(description="Final numeric tier.")]
    project_name: Annotated[str, Field(description="Project identifier.")]
    uploader_email: Annotated[str, Field(description="Uploader's email.")]


class FileRoutingResponse(BaseModel):
    """Response schema for the file_routing method."""

    final_original_uri: Annotated[
        str, Field(description="Final URI of the original doc.")
    ]
    final_sanitized_uri: Annotated[
        Optional[str], Field(description="Final URI of the masked doc (if any).")
    ]


class MetadataBQRequest(BaseModel):
    """Request schema for the metadata_bq method."""

    final_original_uri: Annotated[str, Field(description="Final original URI.")]
    final_sanitized_uri: Annotated[
        Optional[str], Field(description="Final masked URI (if any).")
    ]
    llm_classification: Annotated[
        ContextualClassificationResponse,
        Field(description="Classification results from Gemini."),
    ]
    blob_metadata: Annotated[
        DocumentMetadata, Field(description="Metadata extracted from GCS.")
    ]
