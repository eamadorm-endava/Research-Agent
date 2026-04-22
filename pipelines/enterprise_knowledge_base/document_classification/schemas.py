from pydantic import BaseModel, Field
from typing import Annotated, Optional
from .gcs.schemas import DocumentMetadata
from .gemini.schemas import ContextualClassificationResponse


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
