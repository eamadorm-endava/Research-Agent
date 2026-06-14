from loguru import logger
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from .config import ONEDRIVE_SERVER_CONFIG
from .security import MicrosoftTokenVerifier, create_onedrive_client
from .schemas import (
    FindItemsRequest,
    FindItemsResponse,
    ListFolderContentsRequest,
    ListFolderContentsResponse,
    ReadFileRequest,
    ReadFileResponse,
)

# Instantiate MCP Server
mcp = FastMCP(
    ONEDRIVE_SERVER_CONFIG.server_name,
    stateless_http=ONEDRIVE_SERVER_CONFIG.stateless_http,
    host=ONEDRIVE_SERVER_CONFIG.default_host,
    port=ONEDRIVE_SERVER_CONFIG.default_port,
    token_verifier=MicrosoftTokenVerifier(),
    # Entra ID token validation uses a standard OAuth issuer
    auth=AuthSettings(
        issuer_url=AnyHttpUrl("https://login.microsoftonline.com/common/v2.0"),
        resource_server_url=AnyHttpUrl(
            f"http://{ONEDRIVE_SERVER_CONFIG.default_host}:{ONEDRIVE_SERVER_CONFIG.default_port}"
        ),
    ),
)


@mcp.tool()
async def find_items(request: FindItemsRequest) -> FindItemsResponse:
    """
    Search for items globally across the OneDrive environment.
    Performs fuzzy matching on the item name, bounded by date filters and folder scopes.

    Args:
        request: FindItemsRequest -> The parameters defining the search boundary.

    Returns:
        FindItemsResponse -> A paginated list of matching items, organized structurally.
    """
    logger.info("Tool call: find_items(item_name=%s)", request.item_name)
    try:
        client = create_onedrive_client()
        return await client.find_items(request)
    except Exception as exc:
        logger.exception("Error during find_items execution")
        return FindItemsResponse(
            execution_status="error",
            execution_message=f"Error finding items: {str(exc)}",
            total_search_matches=0,
            total_pages=0,
            current_page=0,
            items_in_page=0,
            objects_found=[],
        )


@mcp.tool()
async def list_folder_contents(
    request: ListFolderContentsRequest,
) -> ListFolderContentsResponse:
    """
    List the explicit contents of a targeted OneDrive folder.
    Browses one directory level deep without recursive fuzzy searching.

    Args:
        request: ListFolderContentsRequest -> The parameters identifying the folder.

    Returns:
        ListFolderContentsResponse -> A paginated list of explicit child items within the folder.
    """
    logger.info("Tool call: list_folder_contents(folder_id=%s)", request.folder_id)
    try:
        client = create_onedrive_client()
        return await client.list_folder_contents(request)
    except Exception as exc:
        logger.exception("Error during list_folder_contents execution")
        return ListFolderContentsResponse(
            execution_status="error",
            execution_message=f"Error listing folder contents: {str(exc)}",
            total_items_in_folder=0,
            total_pages=0,
            current_page=0,
            items_in_page=0,
            objects_found=[],
        )


@mcp.tool()
async def read_file(request: ReadFileRequest) -> ReadFileResponse:
    """
    Read and ingest a specific file from OneDrive into the GCS Landing Zone.
    Zero-copy streaming bypasses local memory and provisions direct multimodal ingestion.

    Args:
        request: ReadFileRequest -> The parameters pinpointing the target file.

    Returns:
        ReadFileResponse -> The landing zone URI and ingestion metadata.
    """
    logger.info("Tool call: read_file(file_id=%s)", request.file_id)
    try:
        client = create_onedrive_client()
        return await client.read_file(request)
    except Exception as exc:
        logger.exception("Error during read_file execution")
        return ReadFileResponse(
            execution_status="error",
            execution_message=f"Error reading file: {str(exc)}",
            gcs_uri=None,
            mime_type=None,
            filename=None,
            inject_file_data=False,
        )
