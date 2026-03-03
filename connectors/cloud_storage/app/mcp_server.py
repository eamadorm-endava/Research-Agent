from mcp.server import Server
from app.gcs_client import GCSManager
import logging
from typing import Optional, Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

# Instantiate MCP Server
mcp = Server("gcs-mcp-server")

# Instantiate GCS Manager (Relies on Application Default Credentials natively)
gcs_manager = GCSManager()

@mcp.tool()
def create_bucket(bucket_name: str, location: str = "US") -> str:
    """
    Creates a new Google Cloud Storage bucket.
    
    Args:
        bucket_name (str): The name of the bucket to create. Must be globally unique.
        location (str): The GCS location (e.g., 'US', 'EU', 'asia-northeast1'). Defaults to 'US'.
        
    Returns:
        str: Success message with the bucket name.
    """
    logger.info(f"Tool call: create_bucket(bucket_name={bucket_name}, location={location})")
    name = gcs_manager.create_bucket(bucket_name, location)
    return f"Successfully created bucket: {name}"

@mcp.tool()
def update_bucket_labels(bucket_name: str, labels: Dict[str, str]) -> str:
    """
    Updates or sets labels on an existing GCS bucket.
    
    Args:
        bucket_name (str): The name of the bucket.
        labels (Dict[str, str]): A dictionary of key-value pairs to set as labels.
        
    Returns:
        str: Success message with the updated labels.
    """
    logger.info(f"Tool call: update_bucket_labels(bucket_name={bucket_name}, labels={labels})")
    updated_labels = gcs_manager.update_bucket_labels(bucket_name, labels)
    return f"Successfully updated labels for {bucket_name}: {updated_labels}"

@mcp.tool()
def upload_object(
    bucket_name: str, 
    object_name: str, 
    content: Optional[str] = None, 
    local_path: Optional[str] = None,
    content_type: Optional[str] = None
) -> str:
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
    logger.info(f"Tool call: upload_object(bucket_name={bucket_name}, object_name={object_name})")
    # GCSManager handles bytes convertion if we pass it, but MCP string input is fine.
    # If the agent needs to upload bytes, it will likely be passed as a string/hex or handled externally.
    # For now, we support string content and file paths as per AC.
    blob = gcs_manager.create_object(
        bucket_name=bucket_name, 
        object_name=object_name, 
        content=content, 
        local_path=local_path,
        content_type=content_type
    )
    return f"Successfully uploaded object: {blob.name} to bucket: {bucket_name} (Type: {blob.content_type})"

@mcp.tool()
def read_object(bucket_name: str, object_name: str) -> str:
    """
    Downloads a specific file (blob) from a bucket and returns its contents.
    Ideal for reading configuration or documentation files stored in GCS.
    
    Args:
        bucket_name (str): The name of the bucket.
        object_name (str): The name/path of the object to read.
        
    Returns:
        str: The content of the object (decoded as UTF-8 if possible).
    """
    logger.info(f"Tool call: read_object(bucket_name={bucket_name}, object_name={object_name})")
    content_bytes = gcs_manager.download_object_as_bytes(bucket_name, object_name)
    try:
        return content_bytes.decode('utf-8')
    except UnicodeDecodeError:
        return f"[Binary Content] Size: {len(content_bytes)} bytes. (Cannot decode as UTF-8)"

@mcp.tool()
def update_object_metadata(bucket_name: str, object_name: str, metadata: Dict[str, Any]) -> str:
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
    logger.info(f"Tool call: update_object_metadata(bucket_name={bucket_name}, object_name={object_name})")
    blob = gcs_manager.update_object_metadata(bucket_name, object_name, metadata)
    return f"Successfully updated metadata for {object_name}. New content-type: {blob.content_type}"

@mcp.tool()
def delete_object(bucket_name: str, object_name: str) -> str:
    """
    Deletes an object from a GCS bucket.
    
    Args:
        bucket_name (str): The name of the bucket.
        object_name (str): The name/path of the object to delete.
        
    Returns:
        str: Success message.
    """
    logger.info(f"Tool call: delete_object(bucket_name={bucket_name}, object_name={object_name})")
    gcs_manager.delete_object(bucket_name, object_name)
    return f"Successfully deleted object: {object_name} from bucket: {bucket_name}"

@mcp.tool()
def list_objects(bucket_name: str, prefix: Optional[str] = None) -> str:
    """
    Lists objects in a GCS bucket, optionally filtered by prefix to simulate folders.
    
    Args:
        bucket_name (str): The name of the bucket.
        prefix (str, optional): A prefix to filter results (e.g., 'docs/').
        
    Returns:
        str: A message listing the found object names.
    """
    logger.info(f"Tool call: list_objects(bucket_name={bucket_name}, prefix={prefix})")
    blobs = gcs_manager.list_blobs(bucket_name, prefix)
    if not blobs:
        return f"No objects found in bucket {bucket_name} with prefix '{prefix or ''}'."
    return f"Objects in {bucket_name} (prefix='{prefix or ''}'): " + ", ".join(blobs)
