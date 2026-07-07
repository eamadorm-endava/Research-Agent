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


class SubmitKBIngestionFile(BaseModel):
    """Confirmed metadata and artifact name for one KB ingestion file."""

    filename: Annotated[
        str, Field(description="Filename of the uploaded PDF artifact to ingest")
    ]
    project: Annotated[
        str, Field(description="User-confirmed EKB project name for this file")
    ]
    domain: Annotated[
        Literal["IT", "Finance", "HR", "Sales", "Executives", "Legal", "Operations"],
        Field(description="User-confirmed business domain metadata"),
    ]
    trust_level: Annotated[
        Literal["Published", "WIP", "Archived"],
        Field(description="User-confirmed trust-level metadata"),
    ]
    pii_status: Annotated[
        Literal["Yes", "No"],
        Field(description="User-confirmed PII metadata"),
    ]
    version: Annotated[
        Optional[int],
        Field(
            default=None,
            description="Optional artifact version to ingest when the session has multiple versions",
        ),
    ]


class SubmitKBIngestionBatchRequest(BaseModel):
    """Request schema for staging files and starting EKB ingestion jobs."""

    files: Annotated[
        list[SubmitKBIngestionFile],
        Field(description="Confirmed files and metadata to submit", min_length=1),
    ]
    destination_bucket: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional KB landing-zone bucket override. Defaults to '<PROJECT_ID>-kb-landing-zone'.",
        ),
    ]


class SingleSubmitKBIngestionResponse(BaseToolResponse):
    """Result for one file submitted through the unified KB ingestion tool."""

    filename: Annotated[str, Field(description="Submitted filename")]
    project: Annotated[str, Field(description="Confirmed EKB project name")]
    source_uri: Annotated[
        Optional[GcsUri], Field(default=None, description="Original artifact GCS URI")
    ]
    destination_uri: Annotated[
        Optional[GcsUri], Field(default=None, description="KB landing-zone GCS URI")
    ]
    job_id: JobId
    job_status: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Initial ingestion job status returned by the EKB pipeline",
        ),
    ]


class SubmitKBIngestionBatchResponse(BaseModel):
    """Batch result from staging files and triggering EKB ingestion jobs."""

    successful_jobs: Annotated[int, Field(description="Number of jobs started")]
    failed_jobs: Annotated[
        int, Field(description="Number of files that failed before or during trigger")
    ]
    file_responses: Annotated[
        list[SingleSubmitKBIngestionResponse],
        Field(description="Per-file submission, staging, and initial job results"),
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
