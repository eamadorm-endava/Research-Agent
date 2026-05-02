from typing import Annotated, Optional, Any
from pydantic import BaseModel, Field


class TriggerEKBPipelineRequest(BaseModel):
    """Input schema for triggering the EKB ingestion pipeline."""

    gcs_uri: Annotated[
        str,
        Field(
            description="The canonical GCS URI of the document to ingest (gs://...).",
            pattern=r"^gs://[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]/.+$",
        ),
    ]


class TriggerEKBPipelineResponse(BaseModel):
    """Output schema for the EKB ingestion pipeline trigger."""

    execution_status: Annotated[
        str, Field(description="Status of the tool execution (success/error).")
    ]
    execution_message: Annotated[
        str, Field(description="Human-readable execution details.")
    ]
    response: Annotated[
        Optional[dict[str, Any]],
        Field(default=None, description="The raw response from the pipeline service."),
    ]
