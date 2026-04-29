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
    source_uri: Annotated[
        str,
        Field(
            description="The source GCS URI (must start with gs://).",
            pattern=r"^gs://.+$",
        ),
    ]
    destination_bucket: BUCKET_NAME
    path_inside_destination_bucket: Annotated[
        Optional[str],
        Field(
            default="",
            description="Optional path/prefix inside the destination bucket. Do not include leading or trailing slashes.",
        ),
    ]
    name_of_the_file: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional filename without extension. If not provided, the source filename is used.",
        ),
    ]
    metadata: Annotated[
        Dict[str, Any],
        Field(
            default_factory=dict,
            description=(
                "Optional metadata for the file. The 'uploader' field will be "
                "automatically set to the user's email."
            ),
        ),
    ]


class UploadObjectResponse(BaseResponse):
    gcs_uri: Annotated[
        str,
        Field(description="The new GCS URI of the uploaded file."),
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
