from pydantic import BaseModel, Field
from typing import Annotated


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
    latest: Annotated[bool, Field(description="Whether this is the latest version.")]
    ingested_at: Annotated[str, Field(description="ISO 8601 ingestion timestamp.")]
