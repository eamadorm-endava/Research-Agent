from typing import Annotated, Optional
from pydantic import BaseModel, Field

JobIdType = Annotated[str, Field(description="Unique identifier for the ingestion job")]

GcsUri = Annotated[
    str,
    Field(
        description="Canonical GCS URI of the document (gs://bucket/project/file.pdf)",
        pattern=r"^gs://[a-z0-9_\-\.]+/.*$",
    ),
]


class TriggerEKBPipelineBatchRequest(BaseModel):
    """Request schema for triggering the EKB pipeline for one or more files."""

    gcs_uris: Annotated[
        list[GcsUri],
        Field(description="One or more canonical GCS URIs to ingest", min_length=1),
    ]


class TriggerEKBPipelineResponse(BaseModel):
    """Per-file result from the pipeline trigger tool."""

    execution_status: Annotated[str, Field(description="Success or error status")]
    execution_message: Annotated[str, Field(description="Informational message")]
    job_id: JobIdType
    gcs_uri: Annotated[
        Optional[str], Field(description="The GCS URI that was triggered", default=None)
    ]
    response: Annotated[
        Optional[dict],
        Field(description="Raw response from service", default=None),
    ]


class CheckIngestionStatusRequest(BaseModel):
    """Request schema for polling job status."""

    job_id: JobIdType


class CheckIngestionStatusResponse(BaseModel):
    """Unified response for job status checks."""

    job_id: JobIdType
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
