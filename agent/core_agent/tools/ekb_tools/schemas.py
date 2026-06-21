from typing import Annotated, Optional, Literal
from pydantic import BaseModel, Field

JobId = Annotated[
    Optional[str],
    Field(
        default=None,
        description="Unique identifier for the ingestion job",
    ),
]
GcsUri = Annotated[
    str,
    Field(
        description="Canonical GCS URI of the document (gs://bucket/project/file.pdf)",
        pattern=r"^gs://[a-z0-9_\-\.]+/.*$",
    ),
]


class BaseToolResponse(BaseModel):
    """Base response schema for all tools."""

    execution_status: Annotated[
        Literal["success", "error"], Field(description="Status of the tool execution.")
    ]
    execution_message: Annotated[
        str, Field(description="Human-readable message about the operation result.")
    ]


class TriggerEKBPipelineBatchRequest(BaseModel):
    """Request schema for triggering the EKB pipeline for one or more files."""

    gcs_uris: Annotated[
        list[GcsUri],
        Field(description="One or more canonical GCS URIs to ingest", min_length=1),
    ]


class SingleTriggerResponse(BaseToolResponse):
    """
    Result of triggering the pipeline for a single file.
    """

    gcs_uri: Optional[GcsUri]
    job_id: JobId
    job_status: Annotated[
        Optional[str],
        Field(
            description="Status of the ingestion job returned by the pipeline.",
            default=None,
        ),
    ]


class TriggerBatchEKBPipelineResponse(BaseModel):
    """
    Unified result from the batch pipeline trigger tool.
    This class does not need to inherit from BaseToolResponse as it provides
    a summary of the entire batch operation. Each job response has its own
    execution status.
    """

    successful_jobs: Annotated[
        int, Field(description="Number of jobs successfully initiated.")
    ]
    failed_jobs: Annotated[
        int, Field(description="Number of jobs that failed to initiate.")
    ]
    job_responses: Annotated[
        list[SingleTriggerResponse],
        Field(
            description="List of responses from the ingestion pipeline for each triggered file."
        ),
    ]


class CheckIngestionStatusRequest(BaseModel):
    """Request schema for polling job status."""

    job_id: JobId


class CheckIngestionStatusResponse(BaseToolResponse):
    """Unified response for job status checks."""

    job_id: JobId
    job_status: Annotated[str, Field(description="Current job status")]
    job_message: Annotated[str, Field(description="Informational message")]
    gcs_uri: Annotated[
        Optional[GcsUri], Field(description="The final GCS URI", default=None)
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
