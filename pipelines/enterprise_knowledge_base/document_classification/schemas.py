from pydantic import BaseModel, Field
from typing import Annotated, Optional, Literal


class DocumentMetadata(BaseModel):
    """Schema for document metadata extracted from GCS."""

    filename: Annotated[str, Field(description="The name of the file.")]
    mime_type: Annotated[str, Field(description="The MIME type of the content.")]
    proposed_domain: Annotated[
        Optional[str],
        Field(description="The detected or proposed domain.", default=None),
    ]
    trust_level: Annotated[
        Optional[str],
        Field(
            description="The trust maturity level (published, wip, archived).",
            default=None,
        ),
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


class DLPTriggerRequest(BaseModel):
    """Request schema for the DLP trigger phase."""

    landing_zone_original_uri: Annotated[
        str, Field(description="The URI of the original document in GCS.")
    ]


class DLPTriggerResponse(BaseModel):
    """Schema for the response of the DLP trigger pipeline."""

    sanitized_gcs_uri: Annotated[
        str, Field(description="The URI of the sanitized/masked document.")
    ]
    proposed_classification_tier: Annotated[
        Optional[int],
        Field(description="The suggested classification tier (1-5).", default=None),
    ]


class ContextualClassificationRequest(BaseModel):
    """Request schema for the Gemini contextual classification phase."""

    sanitized_url: Annotated[
        str, Field(description="The URI of the sanitized/masked document.")
    ]
    proposed_classification_tier: Annotated[
        Optional[int],
        Field(description="The suggested classification tier (1-5).", default=None),
    ]
    proposed_domain: Annotated[
        Optional[str],
        Field(description="The detected or proposed domain.", default=None),
    ]
    trust_level: Annotated[
        Optional[str],
        Field(
            description="The trust maturity level (published, wip, archived).",
            default=None,
        ),
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
