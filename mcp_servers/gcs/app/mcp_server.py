import asyncio
import logging
from mcp.server.fastmcp import FastMCP
from .gcs_client import GCSManager
from .schemas import (
    CreateBucketRequest,
    CreateBucketResponse,
    UpdateBucketLabelsRequest,
    UpdateBucketLabelsResponse,
    UploadObjectRequest,
    UploadObjectResponse,
    ReadObjectRequest,
    ReadObjectResponse,
    UpdateObjectMetadataRequest,
    UpdateObjectMetadataResponse,
    DeleteObjectRequest,
    DeleteObjectResponse,
    ListObjectsRequest,
    ListObjectsResponse,
    ListBucketsRequest,
    ListBucketsResponse,
)

# Configure logging
logger = logging.getLogger(__name__)

# Instantiate MCP Server
mcp = FastMCP(
    "gcs-mcp-server",
    stateless_http=True,
    json_response=True,
    host="0.0.0.0",
    port="8080",
)

# Instantiate GCS Manager (Relies on Application Default Credentials natively)
gcs_manager = GCSManager()


@mcp.tool()
async def create_bucket(request: CreateBucketRequest) -> CreateBucketResponse:
    """
    Creates a new Google Cloud Storage bucket.

    Args:
        bucket_name (str): The name of the bucket to create. Must be globally unique.
        location (str): The GCS location (e.g., 'US', 'EU', 'asia-northeast1'). Defaults to 'US'.

    Returns:
        str: Success message with the bucket name.
    """
    logger.info(
        f"Tool call: create_bucket(bucket_name={request.bucket_name}, location={request.location})"
    )
    try:
        name = await asyncio.to_thread(
            gcs_manager.create_bucket, request.bucket_name, request.location
        )
        return CreateBucketResponse(
            bucket_name=name,
            location=request.location,
            execution_status="success",
            execution_message=f"Successfully created bucket: {name}",
        )
    except Exception as e:
        return CreateBucketResponse(
            bucket_name=request.bucket_name,
            location=request.location,
            execution_status="error",
            execution_message=str(e),
        )


@mcp.tool()
async def update_bucket_labels(
    request: UpdateBucketLabelsRequest,
) -> UpdateBucketLabelsResponse:
    """
    Updates or sets labels on an existing GCS bucket.

    Args:
        bucket_name (str): The name of the bucket.
        labels (Dict[str, str]): A dictionary of key-value pairs to set as labels.

    Returns:
        str: Success message with the updated labels.
    """
    logger.info(
        f"Tool call: update_bucket_labels(bucket_name={request.bucket_name}, labels={request.labels})"
    )
    try:
        updated_labels = await asyncio.to_thread(
            gcs_manager.update_bucket_labels, request.bucket_name, request.labels
        )
        return UpdateBucketLabelsResponse(
            bucket_name=request.bucket_name,
            labels=updated_labels,
            execution_status="success",
            execution_message=(
                f"Successfully updated labels for {request.bucket_name}: {updated_labels}"
            ),
        )
    except Exception as e:
        return UpdateBucketLabelsResponse(
            bucket_name=request.bucket_name,
            labels=request.labels,
            execution_status="error",
            execution_message=str(e),
        )


@mcp.tool()
async def upload_object(request: UploadObjectRequest) -> UploadObjectResponse:
    """
    Uploads a file (blob) to a specified GCS bucket.
    Supports providing content directly as a string or specifying a local file path.

    Args:
        bucket_name (str): The name of the bucket.
        object_name (str): The name/path of the object to create in GCS.
        content (str, optional): The string content to upload.
        local_path (str, optional): The local file path to upload.
        content_type (str, optional): The MIME type of the file. Auto-detected if not provided.

    Returns:
        str: Success message with the object name.
    """
    logger.info(
        f"Tool call: upload_object(bucket_name={request.bucket_name}, object_name={request.object_name})"
    )
    try:
        blob = await asyncio.to_thread(
            gcs_manager.create_object,
            request.bucket_name,
            request.object_name,
            request.content,
            request.local_path,
            request.content_type,
        )
        return UploadObjectResponse(
            bucket_name=request.bucket_name,
            object_name=blob.name,
            content=request.content,
            local_path=request.local_path,
            content_type=blob.content_type,
            execution_status="success",
            execution_message=(
                f"Successfully uploaded object: {blob.name} to bucket: {request.bucket_name}"
            ),
        )
    except Exception as e:
        return UploadObjectResponse(
            bucket_name=request.bucket_name,
            object_name=request.object_name,
            content=request.content,
            local_path=request.local_path,
            content_type=request.content_type,
            execution_status="error",
            execution_message=str(e),
        )


@mcp.tool()
async def read_object(request: ReadObjectRequest) -> ReadObjectResponse:
    """
    Downloads a specific file (blob) from a bucket and returns its contents.
    Ideal for reading configuration or documentation files stored in GCS.

    Args:
        bucket_name (str): The name of the bucket.
        object_name (str): The name/path of the object to read.

    Returns:
        str: The content of the object (decoded as UTF-8 if possible).
    """
    logger.info(
        f"Tool call: read_object(bucket_name={request.bucket_name}, object_name={request.object_name})"
    )
    try:
        content_bytes = await asyncio.to_thread(
            gcs_manager.download_object_as_bytes,
            request.bucket_name,
            request.object_name,
        )
        decoded = None
        is_binary = False
        try:
            decoded = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            is_binary = True

        return ReadObjectResponse(
            bucket_name=request.bucket_name,
            object_name=request.object_name,
            content=decoded,
            size_bytes=len(content_bytes),
            is_binary=is_binary,
            execution_status="success",
            execution_message="Object read successfully.",
        )
    except Exception as e:
        return ReadObjectResponse(
            bucket_name=request.bucket_name,
            object_name=request.object_name,
            content=None,
            size_bytes=0,
            is_binary=False,
            execution_status="error",
            execution_message=str(e),
        )


@mcp.tool()
async def update_object_metadata(
    request: UpdateObjectMetadataRequest,
) -> UpdateObjectMetadataResponse:
    """
    Updates the metadata of an existing object in GCS, such as content-type or custom metadata.

    Args:
        bucket_name (str): The name of the bucket.
        object_name (str): The name of the object.
        metadata (Dict[str, Any]): Dictionary of metadata keys and values to update.
            Use 'content_type' key to change the MIME type.

    Returns:
        str: Success message with updated metadata summary.
    """
    logger.info(
        "Tool call: update_object_metadata("
        f"bucket_name={request.bucket_name}, object_name={request.object_name})"
    )
    try:
        blob = await asyncio.to_thread(
            gcs_manager.update_object_metadata,
            request.bucket_name,
            request.object_name,
            request.metadata,
        )
        return UpdateObjectMetadataResponse(
            bucket_name=request.bucket_name,
            object_name=request.object_name,
            metadata=blob.metadata or {},
            content_type=blob.content_type,
            execution_status="success",
            execution_message=(
                f"Successfully updated metadata for {request.object_name}."
            ),
        )
    except Exception as e:
        return UpdateObjectMetadataResponse(
            bucket_name=request.bucket_name,
            object_name=request.object_name,
            metadata=request.metadata,
            content_type=request.metadata.get("content_type"),
            execution_status="error",
            execution_message=str(e),
        )


@mcp.tool()
async def delete_object(request: DeleteObjectRequest) -> DeleteObjectResponse:
    """
    Deletes an object from a GCS bucket.

    Args:
        bucket_name (str): The name of the bucket.
        object_name (str): The name/path of the object to delete.

    Returns:
        str: Success message.
    """
    logger.info(
        f"Tool call: delete_object(bucket_name={request.bucket_name}, object_name={request.object_name})"
    )
    try:
        await asyncio.to_thread(
            gcs_manager.delete_object, request.bucket_name, request.object_name
        )
        return DeleteObjectResponse(
            bucket_name=request.bucket_name,
            object_name=request.object_name,
            execution_status="success",
            execution_message=(
                f"Successfully deleted object: {request.object_name} from bucket: {request.bucket_name}"
            ),
        )
    except Exception as e:
        return DeleteObjectResponse(
            bucket_name=request.bucket_name,
            object_name=request.object_name,
            execution_status="error",
            execution_message=str(e),
        )


@mcp.tool()
async def list_objects(request: ListObjectsRequest) -> ListObjectsResponse:
    """
    Lists objects in a GCS bucket, optionally filtered by prefix to simulate folders.

    Args:
        bucket_name (str): The name of the bucket.
        prefix (str, optional): A prefix to filter results (e.g., 'docs/').

    Returns:
        str: A message listing the found object names.
    """
    logger.info(
        f"Tool call: list_objects(bucket_name={request.bucket_name}, prefix={request.prefix})"
    )
    try:
        blobs = await asyncio.to_thread(
            gcs_manager.list_blobs, request.bucket_name, request.prefix
        )
        return ListObjectsResponse(
            bucket_name=request.bucket_name,
            prefix=request.prefix,
            objects=blobs,
            execution_status="success",
            execution_message=(
                f"Found {len(blobs)} objects in {request.bucket_name} with prefix '{request.prefix or ''}'."
            ),
        )
    except Exception as e:
        return ListObjectsResponse(
            bucket_name=request.bucket_name,
            prefix=request.prefix,
            objects=[],
            execution_status="error",
            execution_message=str(e),
        )


@mcp.tool()
async def list_buckets(request: ListBucketsRequest) -> ListBucketsResponse:
    """
    Lists buckets available to the current project credentials,
    optionally filtered by bucket-name prefix.

    Args:
        prefix (str, optional): A prefix to filter bucket names.

    Returns:
        ListBucketsResponse: A structured response with matching bucket names.
    """
    logger.info(f"Tool call: list_buckets(prefix={request.prefix})")
    try:
        buckets = await asyncio.to_thread(gcs_manager.list_buckets, request.prefix)
        return ListBucketsResponse(
            prefix=request.prefix,
            buckets=buckets,
            execution_status="success",
            execution_message=(
                f"Found {len(buckets)} buckets with prefix '{request.prefix or ''}'."
            ),
        )
    except Exception as e:
        return ListBucketsResponse(
            prefix=request.prefix,
            buckets=[],
            execution_status="error",
            execution_message=str(e),
        )
