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
    source_gcs_uri: Annotated[
        str,
        Field(
            description="The source GCS URI (gs://bucket/object).",
            pattern=r"^gs://[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]/.+$",
        ),
    ]
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
    def source_bucket(self) -> str:
        """Extracts the bucket name from the source GCS URI."""
        import re

        match = re.match(r"^gs://([^/]+)/", self.source_gcs_uri)
        return match.group(1) if match else ""

    @property
    def source_object(self) -> str:
        """Extracts the object path from the source GCS URI."""
        import re

        match = re.match(r"^gs://[^/]+/(.+)$", self.source_gcs_uri)
        return match.group(1) if match else ""

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
