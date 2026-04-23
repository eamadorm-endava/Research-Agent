from typing import Annotated, Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator

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
OBJECT_METADATA = Annotated[
    Dict[str, str],
    Field(
        default_factory=dict,
        description=(
            "Optional custom metadata to attach to the uploaded object. "
            "Each entry becomes an x-goog-meta-* header in Cloud Storage."
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


class BaseRequest(BaseModel):
    user_identity_context: Annotated[
        Optional[Dict[str, str]],
        Field(
            default=None,
            description=(
                "Optional opaque identity context supplied by the agent "
                "(for example user principal, authorization resource ID, session ID). "
                "Do not include raw bearer tokens in this payload field."
            ),
        ),
    ]


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
    bucket_name: BUCKET_NAME
    object_name: OBJECT_NAME
    content: Annotated[
        Optional[str],
        Field(default=None, description="Inline text content to upload."),
    ]
    content_base64: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Base64-encoded binary payload to upload.",
        ),
    ]
    local_path: Annotated[
        Optional[str],
        Field(default=None, description="Local path to upload from."),
    ]
    content_type: Annotated[
        Optional[str],
        Field(default=None, description="MIME type of the uploaded object."),
    ]
    metadata: OBJECT_METADATA

    @model_validator(mode="after")
    def validate_content_source(self) -> "UploadObjectRequest":
        provided_sources = [
            source
            for source in (self.content, self.content_base64, self.local_path)
            if source is not None
        ]
        if not provided_sources:
            raise ValueError(
                "One of content, content_base64, or local_path must be provided."
            )
        if len(provided_sources) > 1:
            raise ValueError(
                "Provide only one upload source: content, content_base64, or local_path."
            )
        return self


class UploadObjectResponse(UploadObjectRequest, BaseResponse):
    metadata: OBJECT_METADATA
    user_email: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Email extracted from the delegated OAuth token, when available.",
        ),
    ]


class ReadObjectRequest(BaseRequest):
    bucket_name: BUCKET_NAME
    object_name: OBJECT_NAME


class ReadObjectResponse(ReadObjectRequest, BaseResponse):
    content: Annotated[
        Optional[str],
        Field(default=None, description="UTF-8 decoded content when applicable."),
    ]
    size_bytes: Annotated[
        int,
        Field(default=0, description="Object payload size in bytes."),
    ]
    is_binary: Annotated[
        bool,
        Field(default=False, description="True when content is binary/non UTF-8."),
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
