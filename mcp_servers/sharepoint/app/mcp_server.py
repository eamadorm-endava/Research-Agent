from loguru import logger
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from .config import SHAREPOINT_SERVER_CONFIG
from .schemas import (
    DiscoverSharePointSiteContentRequest,
    DiscoverSharePointSiteContentResponse,
    GetSharePointDriveItemRequest,
    GetSharePointDriveItemResponse,
    GetSharePointSitePageRequest,
    GetSharePointSitePageResponse,
    GetSharePointSiteRequest,
    GetSharePointSiteResponse,
    IngestSharePointDriveItemRequest,
    IngestSharePointDriveItemResponse,
    ListSharePointDriveItemsRequest,
    ListSharePointDriveItemsResponse,
    ListSharePointListItemsRequest,
    ListSharePointListItemsResponse,
    ListSharePointSiteDrivesRequest,
    ListSharePointSiteDrivesResponse,
    ListSharePointSiteListsRequest,
    ListSharePointSiteListsResponse,
    ListSharePointSitePagesRequest,
    ListSharePointSitePagesResponse,
    SearchSharePointDriveItemsRequest,
    SearchSharePointDriveItemsResponse,
    SearchSharePointSitesRequest,
    SearchSharePointSitesResponse,
)
from .security import MicrosoftTokenVerifier, create_sharepoint_client


mcp = FastMCP(
    SHAREPOINT_SERVER_CONFIG.server_name,
    stateless_http=SHAREPOINT_SERVER_CONFIG.stateless_http,
    host=SHAREPOINT_SERVER_CONFIG.default_host,
    port=SHAREPOINT_SERVER_CONFIG.default_port,
    token_verifier=MicrosoftTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl("https://login.microsoftonline.com/common/v2.0"),
        resource_server_url=AnyHttpUrl(
            f"http://{SHAREPOINT_SERVER_CONFIG.default_host}:"
            f"{SHAREPOINT_SERVER_CONFIG.default_port}"
        ),
    ),
)


@mcp.tool()
async def search_sharepoint_sites(
    request: SearchSharePointSitesRequest,
) -> SearchSharePointSitesResponse:
    """
    Search SharePoint sites visible to the signed-in Microsoft user.

    Args:
        request: SearchSharePointSitesRequest -> Site search query and pagination.

    Returns:
        SearchSharePointSitesResponse -> Matching site metadata.
    """
    logger.info("Tool call: search_sharepoint_sites(query=%s)", request.query)
    try:
        return await create_sharepoint_client().search_sharepoint_sites(request)
    except Exception as exc:
        logger.exception("Error during search_sharepoint_sites execution")
        return SearchSharePointSitesResponse(
            execution_status="error",
            execution_message=f"Error searching SharePoint sites: {str(exc)}",
            total_items=0,
            total_pages=1,
            current_page=1,
            items_in_page=0,
            sites=[],
        )


@mcp.tool()
async def get_sharepoint_site(
    request: GetSharePointSiteRequest,
) -> GetSharePointSiteResponse:
    """
    Read expanded metadata for one SharePoint site.

    Args:
        request: GetSharePointSiteRequest -> Site identifier.

    Returns:
        GetSharePointSiteResponse -> Expanded site metadata.
    """
    logger.info("Tool call: get_sharepoint_site(site_id=%s)", request.site_id)
    try:
        return await create_sharepoint_client().get_sharepoint_site(request)
    except Exception as exc:
        logger.exception("Error during get_sharepoint_site execution")
        return GetSharePointSiteResponse(
            execution_status="error",
            execution_message=f"Error getting SharePoint site: {str(exc)}",
            site=None,
        )


@mcp.tool()
async def discover_sharepoint_site_content(
    request: DiscoverSharePointSiteContentRequest,
) -> DiscoverSharePointSiteContentResponse:
    """
    Discover site metadata, document libraries, lists, and modern pages.

    Args:
        request: DiscoverSharePointSiteContentRequest -> Site identifier and include flags.

    Returns:
        DiscoverSharePointSiteContentResponse -> Site content overview.
    """
    logger.info(
        "Tool call: discover_sharepoint_site_content(site_id=%s)", request.site_id
    )
    try:
        return await create_sharepoint_client().discover_sharepoint_site_content(
            request
        )
    except Exception as exc:
        logger.exception("Error during discover_sharepoint_site_content execution")
        return DiscoverSharePointSiteContentResponse(
            execution_status="error",
            execution_message=f"Error discovering SharePoint site content: {str(exc)}",
            site=None,
            document_libraries=[],
            lists=[],
            pages=[],
        )


@mcp.tool()
async def list_sharepoint_site_drives(
    request: ListSharePointSiteDrivesRequest,
) -> ListSharePointSiteDrivesResponse:
    """
    List document-library drives available inside a SharePoint site.

    Args:
        request: ListSharePointSiteDrivesRequest -> Site identifier and pagination.

    Returns:
        ListSharePointSiteDrivesResponse -> Document-library drive metadata.
    """
    logger.info("Tool call: list_sharepoint_site_drives(site_id=%s)", request.site_id)
    try:
        return await create_sharepoint_client().list_sharepoint_site_drives(request)
    except Exception as exc:
        logger.exception("Error during list_sharepoint_site_drives execution")
        return ListSharePointSiteDrivesResponse(
            execution_status="error",
            execution_message=f"Error listing SharePoint drives: {str(exc)}",
            total_items=0,
            total_pages=1,
            current_page=1,
            items_in_page=0,
            drives=[],
        )


@mcp.tool()
async def list_sharepoint_site_lists(
    request: ListSharePointSiteListsRequest,
) -> ListSharePointSiteListsResponse:
    """
    List SharePoint lists inside a site.

    Args:
        request: ListSharePointSiteListsRequest -> Site identifier and pagination.

    Returns:
        ListSharePointSiteListsResponse -> SharePoint list metadata.
    """
    logger.info("Tool call: list_sharepoint_site_lists(site_id=%s)", request.site_id)
    try:
        return await create_sharepoint_client().list_sharepoint_site_lists(request)
    except Exception as exc:
        logger.exception("Error during list_sharepoint_site_lists execution")
        return ListSharePointSiteListsResponse(
            execution_status="error",
            execution_message=f"Error listing SharePoint lists: {str(exc)}",
            total_items=0,
            total_pages=1,
            current_page=1,
            items_in_page=0,
            lists=[],
        )


@mcp.tool()
async def list_sharepoint_list_items(
    request: ListSharePointListItemsRequest,
) -> ListSharePointListItemsResponse:
    """
    Read visible field values from a SharePoint list.

    Args:
        request: ListSharePointListItemsRequest -> Site and list identifiers.

    Returns:
        ListSharePointListItemsResponse -> List item field values and previews.
    """
    logger.info("Tool call: list_sharepoint_list_items(list_id=%s)", request.list_id)
    try:
        return await create_sharepoint_client().list_sharepoint_list_items(request)
    except Exception as exc:
        logger.exception("Error during list_sharepoint_list_items execution")
        return ListSharePointListItemsResponse(
            execution_status="error",
            execution_message=f"Error reading SharePoint list items: {str(exc)}",
            total_items=0,
            total_pages=1,
            current_page=1,
            items_in_page=0,
            items=[],
        )


@mcp.tool()
async def list_sharepoint_site_pages(
    request: ListSharePointSitePagesRequest,
) -> ListSharePointSitePagesResponse:
    """
    List modern SharePoint pages in a site.

    Args:
        request: ListSharePointSitePagesRequest -> Site identifier and pagination.

    Returns:
        ListSharePointSitePagesResponse -> Modern page metadata.
    """
    logger.info("Tool call: list_sharepoint_site_pages(site_id=%s)", request.site_id)
    try:
        return await create_sharepoint_client().list_sharepoint_site_pages(request)
    except Exception as exc:
        logger.exception("Error during list_sharepoint_site_pages execution")
        return ListSharePointSitePagesResponse(
            execution_status="error",
            execution_message=f"Error listing SharePoint pages: {str(exc)}",
            total_items=0,
            total_pages=1,
            current_page=1,
            items_in_page=0,
            pages=[],
        )


@mcp.tool()
async def get_sharepoint_site_page(
    request: GetSharePointSitePageRequest,
) -> GetSharePointSitePageResponse:
    """
    Read a modern SharePoint page and extract useful readable text.

    Args:
        request: GetSharePointSitePageRequest -> Site and page identifiers.

    Returns:
        GetSharePointSitePageResponse -> Page metadata and extracted text.
    """
    logger.info("Tool call: get_sharepoint_site_page(page_id=%s)", request.page_id)
    try:
        return await create_sharepoint_client().get_sharepoint_site_page(request)
    except Exception as exc:
        logger.exception("Error during get_sharepoint_site_page execution")
        return GetSharePointSitePageResponse(
            execution_status="error",
            execution_message=f"Error reading SharePoint page: {str(exc)}",
            page=None,
            text="",
            text_char_count=0,
        )


@mcp.tool()
async def list_sharepoint_drive_items(
    request: ListSharePointDriveItemsRequest,
) -> ListSharePointDriveItemsResponse:
    """
    List files and folders from a SharePoint document-library drive.

    Args:
        request: ListSharePointDriveItemsRequest -> Drive ID and optional folder location.

    Returns:
        ListSharePointDriveItemsResponse -> Files and folders in the requested location.
    """
    logger.info("Tool call: list_sharepoint_drive_items(drive_id=%s)", request.drive_id)
    try:
        return await create_sharepoint_client().list_sharepoint_drive_items(request)
    except Exception as exc:
        logger.exception("Error during list_sharepoint_drive_items execution")
        return ListSharePointDriveItemsResponse(
            execution_status="error",
            execution_message=f"Error listing SharePoint drive items: {str(exc)}",
            total_items=0,
            total_pages=1,
            current_page=1,
            items_in_page=0,
            items=[],
        )


@mcp.tool()
async def get_sharepoint_drive_item(
    request: GetSharePointDriveItemRequest,
) -> GetSharePointDriveItemResponse:
    """
    Read metadata for a single SharePoint drive item.

    Args:
        request: GetSharePointDriveItemRequest -> Drive and item identifiers.

    Returns:
        GetSharePointDriveItemResponse -> Drive item metadata.
    """
    logger.info("Tool call: get_sharepoint_drive_item(item_id=%s)", request.item_id)
    try:
        return await create_sharepoint_client().get_sharepoint_drive_item(request)
    except Exception as exc:
        logger.exception("Error during get_sharepoint_drive_item execution")
        return GetSharePointDriveItemResponse(
            execution_status="error",
            execution_message=f"Error getting SharePoint drive item: {str(exc)}",
            item=None,
        )


@mcp.tool()
async def search_sharepoint_drive_items(
    request: SearchSharePointDriveItemsRequest,
) -> SearchSharePointDriveItemsResponse:
    """
    Search files and folders inside a SharePoint document-library drive.

    Args:
        request: SearchSharePointDriveItemsRequest -> Drive ID, query, and pagination.

    Returns:
        SearchSharePointDriveItemsResponse -> Matching drive items.
    """
    logger.info("Tool call: search_sharepoint_drive_items(query=%s)", request.query)
    try:
        return await create_sharepoint_client().search_sharepoint_drive_items(request)
    except Exception as exc:
        logger.exception("Error during search_sharepoint_drive_items execution")
        return SearchSharePointDriveItemsResponse(
            execution_status="error",
            execution_message=f"Error searching SharePoint drive items: {str(exc)}",
            total_items=0,
            total_pages=1,
            current_page=1,
            items_in_page=0,
            items=[],
        )


@mcp.tool()
async def ingest_sharepoint_drive_item(
    request: IngestSharePointDriveItemRequest,
) -> IngestSharePointDriveItemResponse:
    """
    Download one SharePoint file into the internal GCS landing zone.

    Args:
        request: IngestSharePointDriveItemRequest -> Drive/item IDs and session context.

    Returns:
        IngestSharePointDriveItemResponse -> GCS URI and multimodal injection metadata.
    """
    logger.info("Tool call: ingest_sharepoint_drive_item(item_id=%s)", request.item_id)
    try:
        return await create_sharepoint_client().ingest_sharepoint_drive_item(request)
    except Exception as exc:
        logger.exception("Error during ingest_sharepoint_drive_item execution")
        return IngestSharePointDriveItemResponse(
            execution_status="error",
            execution_message=f"Error ingesting SharePoint drive item: {str(exc)}",
            gcs_uri=None,
            mime_type=None,
            filename=None,
            inject_file_data=False,
        )
