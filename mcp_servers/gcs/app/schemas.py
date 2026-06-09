from typing import Annotated, Dict, Optional, Any, List, Literal
from pydantic import BaseModel, Field

from .config import GCS_SERVER_CONFIG


BUCKET_NAME = Annotated[
    str,
    Field(
        description="The GCS bucket name.",
        pattern=r"^[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]$",
        min_length=3,
        max_length=222,
    ),
]
OBJECT_NAME = Annotated[
    str,
    Field(
        description="The object (blob) name/path in the bucket.",
        min_length=1,
        max_length=1024,
    ),
]
LOCATION = Annotated[
    str,
    Field(default="US", description="The geographic location for bucket creation."),
]
PROJECT_ID = Annotated[
    Optional[str],
    Field(
        default=GCS_SERVER_CONFIG.default_project_id,
        description=(
            "Optional GCP project ID for project-scoped bucket operations. "
            "When omitted, the server uses its configured default project."
        ),
    ),
]


class AgentDependencies(BaseModel):
    app_name: Annotated[
        str, Field(description="The name of the calling application or agent.")
    ]
    user_id: Annotated[
        str, Field(description="The unique identifier of the user using the agent")
    ]
    session_id: Annotated[
        str, Field(description="The current session or conversation ID with the agent")
    ]


class BaseRequest(BaseModel):
    dependencies: Annotated[
        Optional[AgentDependencies],
        Field(
            default=None,
            description=(
                """
                SYSTEM FIELD: Do NOT provide this parameter. It is automatically injected by the framework in the ToolWrapper as a dependecy injection.
                """
            ),
        ),
    ]


class BaseResponse(BaseModel):
    execution_status: Annotated[
        Literal["success", "error"],
        Field(description="Execution status for the tool call."),
    ]
    execution_message: Annotated[
        str,
        Field(description="Human-readable execution details."),
    ]


class AuthenticationError(Exception):
    """Raised when delegated OAuth authentication fails."""


class CreateBucketRequest(BaseRequest):
    project_id: PROJECT_ID
    bucket_name: BUCKET_NAME
    location: LOCATION


class CreateBucketResponse(CreateBucketRequest, BaseResponse):
    pass


class UpdateBucketLabelsRequest(BaseRequest):
    bucket_name: BUCKET_NAME
    labels: Annotated[
        Dict[str, str],
        Field(description="Labels to set/overwrite in the target bucket."),
    ]


class UpdateBucketLabelsResponse(UpdateBucketLabelsRequest, BaseResponse):
    pass


class UploadObjectRequest(BaseRequest):
    source_bucket_name: BUCKET_NAME
    source_object_name: OBJECT_NAME
    destination_bucket: BUCKET_NAME
    filename: Annotated[
        str,
        Field(
            description="The mandatory new filename in the destination bucket.",
            min_length=1,
            max_length=1024,
        ),
    ]
    path_inside_bucket: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional folder path inside the destination bucket. Do not include leading/trailing slashes.",
        ),
    ]

    @property
    def destination_path(self) -> str:
        """Constructs the full destination path including filename."""
        path = (self.path_inside_bucket or "").strip("/")
        return f"{path}/{self.filename}" if path else self.filename


class UploadObjectResponse(BaseResponse):
    destination_uri: Annotated[
        str,
        Field(description="The full GCS URI of the ingested object."),
    ]


class ReadObjectRequest(BaseRequest):
    bucket_name: BUCKET_NAME
    object_name: OBJECT_NAME


class GcsObjectMetadata(BaseModel):
    mime_type: Annotated[str, Field(description="MIME type of the object.")]
    size_bytes: Annotated[int, Field(description="Size of the object in bytes.")]
    creation_date: Annotated[str, Field(description="Date of creation (YYYY-MM-DD).")]
    creation_time: Annotated[str, Field(description="Time of creation (HH:MM:SS).")]
    updated_at: Annotated[str, Field(description="Last update timestamp (ISO 8601).")]
    custom_metadata: Annotated[
        Dict[str, str],
        Field(default_factory=dict, description="Custom user-defined metadata."),
    ]


class ReadObjectResponse(BaseResponse):
    gcs_uri: Annotated[str, Field(description="The canonical GCS URI (gs://...).")]
    mime_type: Annotated[str, Field(description="The MIME type of the file.")]
    metadata: Annotated[
        GcsObjectMetadata,
        Field(description="Strictly typed object metadata."),
    ]
    inject_file_data: Annotated[
        bool,
        Field(
            default=True,
            description="Internal flag to trigger zero-copy file ingestion.",
        ),
    ]


class UpdateObjectMetadataRequest(BaseRequest):
    bucket_name: BUCKET_NAME
    object_name: OBJECT_NAME
    metadata: Annotated[
        Dict[str, Any],
        Field(description="Metadata to patch on the target object."),
    ]


class UpdateObjectMetadataResponse(UpdateObjectMetadataRequest, BaseResponse):
    content_type: Annotated[
        Optional[str],
        Field(default=None, description="Updated object MIME type."),
    ]


class DeleteObjectRequest(BaseRequest):
    bucket_name: BUCKET_NAME
    object_name: OBJECT_NAME


class DeleteObjectResponse(DeleteObjectRequest, BaseResponse):
    pass


class ListObjectsRequest(BaseRequest):
    bucket_name: BUCKET_NAME
    prefix: Annotated[
        Optional[str],
        Field(default=None, description="Optional prefix filter."),
    ]


class ListObjectsResponse(ListObjectsRequest, BaseResponse):
    objects: Annotated[
        List[str],
        Field(description="List of object names in the bucket."),
    ]


class ListBucketsRequest(BaseRequest):
    project_id: PROJECT_ID
    prefix: Annotated[
        Optional[str],
        Field(default=None, description="Optional bucket-name prefix filter."),
    ]


class ListBucketsResponse(ListBucketsRequest, BaseResponse):
    buckets: Annotated[
        List[str],
        Field(description="List of bucket names available in the current project."),
    ]
