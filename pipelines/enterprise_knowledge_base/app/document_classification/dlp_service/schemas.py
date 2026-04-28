from pydantic import BaseModel, Field
from typing import Annotated, Optional


class DLPTriggerResponse(BaseModel):
    """Schema for the response of the DLP trigger pipeline."""

    sanitized_gcs_uri: Annotated[
        str, Field(description="The URI of the sanitized/masked document.")
    ]
    proposed_classification_tier: Annotated[
        Optional[int], Field(description="The suggested classification tier (1-5).")
    ]
