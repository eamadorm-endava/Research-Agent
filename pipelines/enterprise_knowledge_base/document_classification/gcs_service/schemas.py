from pydantic import BaseModel, Field
from typing import Annotated, Optional


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
