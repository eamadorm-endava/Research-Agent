from pydantic import BaseModel, Field
from typing import Annotated, Union


class DocumentMetadata(BaseModel):
    """Schema for document metadata extracted from GCS."""

    filename: Annotated[str, Field(description="The name of the file.")]
    mime_type: Annotated[str, Field(description="The MIME type of the content.")]
    proposed_domain: Annotated[
        str, Field(description="The detected or proposed domain.")
    ]
    trust_level: Annotated[
        str, Field(description="The trust maturity level (published, wip, archived).")
    ]
    project_name: Annotated[
        str, Field(description="The associated project identifier.")
    ]
    uploader_email: Annotated[str, Field(description="The email of the uploader.")]
    creator_name: Annotated[str, Field(description="The display name of the creator.")]
    ingested_at: Annotated[
        Union[str, None], Field(description="ISO timestamp of ingestion.")
    ]


class DLPTriggerResponse(BaseModel):
    """Schema for the response of the DLP trigger pipeline."""

    sanitized_gcs_uri: Annotated[
        str, Field(description="The URI of the sanitized/masked document.")
    ]
    proposed_classification_tier: Annotated[
        Union[int, None], Field(description="The suggested classification tier (1-5).")
    ]
