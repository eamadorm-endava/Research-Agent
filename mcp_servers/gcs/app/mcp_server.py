import asyncio
import logging
import re
from typing import Optional

import httpx
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from .config import GCS_API_CONFIG, GCS_AUTH_CONFIG, GCS_SERVER_CONFIG
from .gcs_client import GCSManager, build_gcs_credentials
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


class GoogleGcsTokenVerifier(TokenVerifier):
    """Verifies a Google OAuth access token against Google's tokeninfo endpoint."""

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    GCS_AUTH_CONFIG.google_token_info_url,
                    params={"access_token": token},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return AccessToken(
                        token=token,
                        client_id=data.get("aud", "unknown"),
                        scopes=data.get("scope", "").split(),
                    )
        except Exception:
            pass
        return None


# Instantiate MCP Server
mcp = FastMCP(
    GCS_SERVER_CONFIG.server_name,
    stateless_http=GCS_SERVER_CONFIG.stateless_http,
    json_response=GCS_SERVER_CONFIG.json_response,
    host=GCS_SERVER_CONFIG.default_host,
    port=GCS_SERVER_CONFIG.default_port,
    debug=GCS_SERVER_CONFIG.debug,
    token_verifier=GoogleGcsTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(GCS_AUTH_CONFIG.google_accounts_issuer_url),
        resource_server_url=AnyHttpUrl(
            f"http://{GCS_SERVER_CONFIG.default_host}:{GCS_SERVER_CONFIG.default_port}"
        ),
    ),
)


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
        "Tool call: create_bucket("
        f"project_id={request.project_id}, bucket_name={request.bucket_name}, "
        f"location={request.location})"
    )
    try:
        gcs_manager = _make_gcs_manager()
        name = await asyncio.to_thread(
            gcs_manager.create_bucket,
            request.bucket_name,
            request.location,
            request.project_id,
        )
        return CreateBucketResponse(
            project_id=request.project_id,
            bucket_name=name,
            location=request.location,
            execution_status="success",
            execution_message=(
                f"Successfully created bucket: {name} in project "
                f"{gcs_manager.resolve_project_id(request.project_id)}"
            ),
        )
    except Exception as e:
        return CreateBucketResponse(
            project_id=request.project_id,
            bucket_name=request.bucket_name,
            location=request.location,
            execution_status="error",
            execution_message=_format_execution_error(e),
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
        gcs_manager = _make_gcs_manager()
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
            execution_message=_format_execution_error(e),
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
        gcs_manager = _make_gcs_manager()
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
            execution_message=_format_execution_error(e),
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
        gcs_manager = _make_gcs_manager()
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
            execution_message=_format_execution_error(e),
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
        gcs_manager = _make_gcs_manager()
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
            execution_message=_format_execution_error(e),
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
        gcs_manager = _make_gcs_manager()
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
            execution_message=_format_execution_error(e),
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
        gcs_manager = _make_gcs_manager()
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
            execution_message=_format_execution_error(e),
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
    logger.info(
        f"Tool call: list_buckets(project_id={request.project_id}, prefix={request.prefix})"
    )
    try:
        gcs_manager = _make_gcs_manager()
        buckets = await asyncio.to_thread(
            gcs_manager.list_buckets, request.prefix, request.project_id
        )
        return ListBucketsResponse(
            project_id=request.project_id,
            prefix=request.prefix,
            buckets=buckets,
            execution_status="success",
            execution_message=(
                f"Found {len(buckets)} buckets with prefix '{request.prefix or ''}' "
                f"in project {gcs_manager.resolve_project_id(request.project_id)}."
            ),
        )
    except Exception as e:
        return ListBucketsResponse(
            project_id=request.project_id,
            prefix=request.prefix,
            buckets=[],
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


def _make_gcs_manager() -> GCSManager:
    """Creates a GCS manager using the delegated user token from MCP context."""
    access_token = _get_current_token()
    creds = build_gcs_credentials(
        access_token=access_token,
        scopes=GCS_API_CONFIG.read_write_scopes,
    )
    return GCSManager(creds, default_project=GCS_SERVER_CONFIG.default_project_id)


def _get_current_token() -> Optional[str]:
    """Returns the currently authenticated OAuth access token from MCP auth context."""
    token_obj = get_access_token()
    return token_obj.token if token_obj else None


def _format_execution_error(exc: Exception) -> str:
    """Returns a sanitized, user-facing execution message with permission normalization."""
    raw_message = _sanitize_sensitive_text(str(exc))
    lowered = raw_message.lower()
    if any(
        marker in lowered
        for marker in (
            "permission denied",
            "access denied",
            "insufficient permission",
            "insufficient permissions",
            "not authorized",
            "forbidden",
            "403",
        )
    ):
        return f"Permission Denied: {raw_message}"
    if any(marker in lowered for marker in ("not found", "404", "no such object")):
        return f"Object not found: {raw_message}"
    return raw_message


def _sanitize_sensitive_text(value: str) -> str:
    """Redacts common credential fragments from error messages before returning them."""
    sanitized = value or ""
    sanitized = re.sub(
        r"Bearer\s+[A-Za-z0-9._\-~+/]+=*", "Bearer [REDACTED]", sanitized
    )
    sanitized = re.sub(r"ya29\.[A-Za-z0-9._\-~+/]+=*", "ya29.[REDACTED]", sanitized)
    sanitized = re.sub(r"access_token=[^&\s]+", "access_token=[REDACTED]", sanitized)
    return sanitized
