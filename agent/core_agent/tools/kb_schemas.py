from typing import Annotated, Optional
from pydantic import BaseModel, Field


class TriggerEKBPipelineRequest(BaseModel):
    """Request schema for triggering the EKB pipeline."""

    gcs_uri: Annotated[
        str,
        Field(
            description="The canonical GCS URI of the document (gs://bucket/project/file.pdf)",
            pattern=r"^gs://[a-z0-9_\-\.]+/.*$",
        ),
    ]

    @property
    def filename(self) -> str:
        """Extracts the filename from the GCS URI."""
        return self.gcs_uri.split("/")[-1]


class TriggerEKBPipelineResponse(BaseModel):
    """Response schema from the agent's trigger tool (Sync wrapper)."""

    execution_status: Annotated[str, Field(description="Success or error status")]
    execution_message: Annotated[str, Field(description="Informational message")]
    job_id: Annotated[Optional[str], Field(description="The background Job ID")] = None
    response: Annotated[
        Optional[dict], Field(description="Raw response from service")
    ] = None


class CheckIngestionStatusRequest(BaseModel):
    """Request schema for polling job status."""

    job_id: Annotated[str, Field(description="The unique Job ID to check")]


class CheckIngestionStatusResponse(BaseModel):
    """Unified response for job status checks."""

    job_id: Annotated[str, Field(description="The unique Job ID")]
    status: Annotated[str, Field(description="Current job status")]
    message: Annotated[str, Field(description="Informational message")]
    gcs_uri: Annotated[
        Optional[str], Field(description="The final GCS URI", default=None)
    ]
    chunks_generated: Annotated[
        Optional[int], Field(description="Number of chunks created", default=None)
    ]
    final_domain: Annotated[
        Optional[str], Field(description="The determined domain", default=None)
    ]
    security_tier: Annotated[
        Optional[str], Field(description="The security tier label", default=None)
    ]
    execution_status: Annotated[
        str, Field(description="Tool execution status", default="success")
    ]
    execution_message: Annotated[
        str, Field(description="Tool execution message", default="")
    ]
