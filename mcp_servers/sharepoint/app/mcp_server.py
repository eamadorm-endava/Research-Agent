import asyncio
import re

from loguru import logger
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from .config import MICROSOFT_AUTH_CONFIG, SHAREPOINT_SERVER_CONFIG
from .schemas import (
    DiscoverSiteContentRequest,
    DiscoverSiteContentResponse,
    GetDriveItemRequest,
    GetDriveItemResponse,
    GetSitePageRequest,
    GetSitePageResponse,
    GetSiteRequest,
    GetSiteResponse,
    IngestDriveItemRequest,
    IngestDriveItemResponse,
    ListDriveItemsRequest,
    ListDriveItemsResponse,
    ListListItemsRequest,
    ListListItemsResponse,
    ListSiteDrivesRequest,
    ListSiteDrivesResponse,
    ListSiteListsRequest,
    ListSiteListsResponse,
    ListSitePagesRequest,
    ListSitePagesResponse,
    SearchDriveItemsRequest,
    SearchDriveItemsResponse,
    SearchSitesRequest,
    SearchSitesResponse,
)
from .security import SharePointTokenVerifier, create_sharepoint_client


mcp = FastMCP(
    SHAREPOINT_SERVER_CONFIG.server_name,
    stateless_http=SHAREPOINT_SERVER_CONFIG.stateless_http,
    json_response=SHAREPOINT_SERVER_CONFIG.json_response,
    host=SHAREPOINT_SERVER_CONFIG.default_host,
    port=SHAREPOINT_SERVER_CONFIG.default_port,
    debug=SHAREPOINT_SERVER_CONFIG.debug,
    token_verifier=SharePointTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(MICROSOFT_AUTH_CONFIG.issuer_url),
        resource_server_url=AnyHttpUrl(
            f"http://{SHAREPOINT_SERVER_CONFIG.default_host}:"
            f"{SHAREPOINT_SERVER_CONFIG.default_port}"
        ),
    ),
)


@mcp.tool()
async def search_sharepoint_sites(request: SearchSitesRequest) -> SearchSitesResponse:
    """Searches SharePoint sites visible to the signed-in user.

    Args:
        request: SearchSitesRequest -> Search text and result limit.

    Returns:
        SearchSitesResponse -> Matching SharePoint site metadata.
    """
    logger.info("Tool call: search_sharepoint_sites(query={})", request.query)
    try:
        client = create_sharepoint_client()
        sites = await asyncio.to_thread(
            client.search_sites,
            query=request.query,
            max_results=request.max_results,
        )
        return SearchSitesResponse(
            query=request.query,
            sites=sites,
            execution_status="success",
            execution_message=f"Found {len(sites)} SharePoint sites.",
        )
    except Exception as exc:
        return SearchSitesResponse(
            query=request.query,
            sites=[],
            execution_status="error",
            execution_message=_format_execution_error(exc),
        )


@mcp.tool()
async def get_sharepoint_site(request: GetSiteRequest) -> GetSiteResponse:
    """Reads expanded metadata for one SharePoint site.

    Args:
        request: GetSiteRequest -> Site ID from search results or user input.

    Returns:
        GetSiteResponse -> Expanded SharePoint site metadata.
    """
    logger.info("Tool call: get_sharepoint_site(site_id={})", request.site_id)
    try:
        client = create_sharepoint_client()
        site = await asyncio.to_thread(client.get_site, site_id=request.site_id)
        return GetSiteResponse(
            site_id=request.site_id,
            site=site,
            execution_status="success",
            execution_message=f"Retrieved SharePoint site {request.site_id}.",
        )
    except Exception as exc:
        return GetSiteResponse(
            site_id=request.site_id,
            site=None,
            execution_status="error",
            execution_message=_format_execution_error(exc),
        )


@mcp.tool()
async def discover_sharepoint_site_content(
    request: DiscoverSiteContentRequest,
) -> DiscoverSiteContentResponse:
    """Lists useful content containers inside a SharePoint site.

    Args:
        request: DiscoverSiteContentRequest -> Site ID and per-container result limit.

    Returns:
        DiscoverSiteContentResponse -> Site metadata, libraries, lists, and pages.
    """
    logger.info(
        "Tool call: discover_sharepoint_site_content(site_id={})", request.site_id
    )
    try:
        client = create_sharepoint_client()
        overview = await asyncio.to_thread(
            client.discover_site_content,
            site_id=request.site_id,
            max_results=request.max_results,
        )
        return DiscoverSiteContentResponse(
            site_id=request.site_id,
            overview=overview,
            execution_status="success",
            execution_message="Retrieved SharePoint site content overview.",
        )
    except Exception as exc:
        return DiscoverSiteContentResponse(
            site_id=request.site_id,
            overview=None,
            execution_status="error",
            execution_message=_format_execution_error(exc),
        )


@mcp.tool()
async def list_sharepoint_site_drives(
    request: ListSiteDrivesRequest,
) -> ListSiteDrivesResponse:
    """Lists document-library drives for a SharePoint site.

    Args:
        request: ListSiteDrivesRequest -> Site ID and result limit.

    Returns:
        ListSiteDrivesResponse -> Available SharePoint document libraries.
    """
    logger.info("Tool call: list_sharepoint_site_drives(site_id={})", request.site_id)
    try:
        client = create_sharepoint_client()
        drives = await asyncio.to_thread(
            client.list_site_drives,
            site_id=request.site_id,
            max_results=request.max_results,
        )
        return ListSiteDrivesResponse(
            site_id=request.site_id,
            drives=drives,
            execution_status="success",
            execution_message=f"Found {len(drives)} SharePoint drives.",
        )
    except Exception as exc:
        return ListSiteDrivesResponse(
            site_id=request.site_id,
            drives=[],
            execution_status="error",
            execution_message=_format_execution_error(exc),
        )


@mcp.tool()
async def list_sharepoint_site_lists(
    request: ListSiteListsRequest,
) -> ListSiteListsResponse:
    """Lists SharePoint lists inside a site.

    Args:
        request: ListSiteListsRequest -> Site ID and result limit.

    Returns:
        ListSiteListsResponse -> Available SharePoint lists.
    """
    logger.info("Tool call: list_sharepoint_site_lists(site_id={})", request.site_id)
    try:
        client = create_sharepoint_client()
        lists = await asyncio.to_thread(
            client.list_site_lists,
            site_id=request.site_id,
            max_results=request.max_results,
        )
        return ListSiteListsResponse(
            site_id=request.site_id,
            lists=lists,
            execution_status="success",
            execution_message=f"Found {len(lists)} SharePoint lists.",
        )
    except Exception as exc:
        return ListSiteListsResponse(
            site_id=request.site_id,
            lists=[],
            execution_status="error",
            execution_message=_format_execution_error(exc),
        )


@mcp.tool()
async def list_sharepoint_list_items(
    request: ListListItemsRequest,
) -> ListListItemsResponse:
    """Lists readable field values from a SharePoint list.

    Args:
        request: ListListItemsRequest -> Site ID, list ID, and result limit.

    Returns:
        ListListItemsResponse -> SharePoint list item fields.
    """
    logger.info("Tool call: list_sharepoint_list_items(list_id={})", request.list_id)
    try:
        client = create_sharepoint_client()
        items = await asyncio.to_thread(
            client.list_list_items,
            site_id=request.site_id,
            list_id=request.list_id,
            max_results=request.max_results,
        )
        return ListListItemsResponse(
            site_id=request.site_id,
            list_id=request.list_id,
            items=items,
            execution_status="success",
            execution_message=f"Found {len(items)} SharePoint list items.",
        )
    except Exception as exc:
        return ListListItemsResponse(
            site_id=request.site_id,
            list_id=request.list_id,
            items=[],
            execution_status="error",
            execution_message=_format_execution_error(exc),
        )


@mcp.tool()
async def list_sharepoint_site_pages(
    request: ListSitePagesRequest,
) -> ListSitePagesResponse:
    """Lists modern SharePoint pages inside a site.

    Args:
        request: ListSitePagesRequest -> Site ID and result limit.

    Returns:
        ListSitePagesResponse -> SharePoint page summaries.
    """
    logger.info("Tool call: list_sharepoint_site_pages(site_id={})", request.site_id)
    try:
        client = create_sharepoint_client()
        pages = await asyncio.to_thread(
            client.list_site_pages,
            site_id=request.site_id,
            max_results=request.max_results,
        )
        return ListSitePagesResponse(
            site_id=request.site_id,
            pages=pages,
            execution_status="success",
            execution_message=f"Found {len(pages)} SharePoint pages.",
        )
    except Exception as exc:
        return ListSitePagesResponse(
            site_id=request.site_id,
            pages=[],
            execution_status="error",
            execution_message=_format_execution_error(exc),
        )


@mcp.tool()
async def get_sharepoint_site_page(
    request: GetSitePageRequest,
) -> GetSitePageResponse:
    """Reads a SharePoint site page and extracts useful text.

    Args:
        request: GetSitePageRequest -> Site ID, page ID, and text limit.

    Returns:
        GetSitePageResponse -> Page metadata and extracted text.
    """
    logger.info("Tool call: get_sharepoint_site_page(page_id={})", request.page_id)
    try:
        client = create_sharepoint_client()
        page = await asyncio.to_thread(
            client.get_site_page,
            site_id=request.site_id,
            page_id=request.page_id,
            max_text_chars=request.max_text_chars,
        )
        return GetSitePageResponse(
            site_id=request.site_id,
            page_id=request.page_id,
            page=page,
            execution_status="success",
            execution_message=f"Retrieved SharePoint page {request.page_id}.",
        )
    except Exception as exc:
        return GetSitePageResponse(
            site_id=request.site_id,
            page_id=request.page_id,
            page=None,
            execution_status="error",
            execution_message=_format_execution_error(exc),
        )


@mcp.tool()
async def list_sharepoint_drive_items(
    request: ListDriveItemsRequest,
) -> ListDriveItemsResponse:
    """Lists children from a SharePoint drive folder.

    Args:
        request: ListDriveItemsRequest -> Drive ID, optional folder selector, and limit.

    Returns:
        ListDriveItemsResponse -> Child file and folder metadata.
    """
    logger.info("Tool call: list_sharepoint_drive_items(drive_id={})", request.drive_id)
    try:
        client = create_sharepoint_client()
        items = await asyncio.to_thread(
            client.list_drive_items,
            drive_id=request.drive_id,
            item_id=request.item_id,
            folder_path=request.normalized_folder_path,
            max_results=request.max_results,
        )
        return ListDriveItemsResponse(
            drive_id=request.drive_id,
            item_id=request.item_id,
            folder_path=request.folder_path,
            items=items,
            execution_status="success",
            execution_message=f"Found {len(items)} SharePoint drive items.",
        )
    except Exception as exc:
        return ListDriveItemsResponse(
            drive_id=request.drive_id,
            item_id=request.item_id,
            folder_path=request.folder_path,
            items=[],
            execution_status="error",
            execution_message=_format_execution_error(exc),
        )


@mcp.tool()
async def get_sharepoint_drive_item(
    request: GetDriveItemRequest,
) -> GetDriveItemResponse:
    """Reads metadata for one SharePoint drive item.

    Args:
        request: GetDriveItemRequest -> Drive ID and item ID.

    Returns:
        GetDriveItemResponse -> Single drive item metadata record.
    """
    logger.info("Tool call: get_sharepoint_drive_item(item_id={})", request.item_id)
    try:
        client = create_sharepoint_client()
        item = await asyncio.to_thread(
            client.get_drive_item,
            drive_id=request.drive_id,
            item_id=request.item_id,
        )
        return GetDriveItemResponse(
            drive_id=request.drive_id,
            item_id=request.item_id,
            item=item,
            execution_status="success",
            execution_message=f"Retrieved SharePoint item {request.item_id}.",
        )
    except Exception as exc:
        return GetDriveItemResponse(
            drive_id=request.drive_id,
            item_id=request.item_id,
            item=None,
            execution_status="error",
            execution_message=_format_execution_error(exc),
        )


@mcp.tool()
async def search_sharepoint_drive_items(
    request: SearchDriveItemsRequest,
) -> SearchDriveItemsResponse:
    """Searches files and folders in a SharePoint drive.

    Args:
        request: SearchDriveItemsRequest -> Drive ID, search text, and limit.

    Returns:
        SearchDriveItemsResponse -> Matching drive items.
    """
    logger.info("Tool call: search_sharepoint_drive_items(query={})", request.query)
    try:
        client = create_sharepoint_client()
        items = await asyncio.to_thread(
            client.search_drive_items,
            drive_id=request.drive_id,
            query=request.query,
            max_results=request.max_results,
        )
        return SearchDriveItemsResponse(
            drive_id=request.drive_id,
            query=request.query,
            items=items,
            execution_status="success",
            execution_message=f"Found {len(items)} SharePoint drive items.",
        )
    except Exception as exc:
        return SearchDriveItemsResponse(
            drive_id=request.drive_id,
            query=request.query,
            items=[],
            execution_status="error",
            execution_message=_format_execution_error(exc),
        )


@mcp.tool()
async def ingest_sharepoint_drive_item(
    request: IngestDriveItemRequest,
) -> IngestDriveItemResponse:
    """Copies one SharePoint file to the internal GCS landing zone.

    The SharePoint side remains read-only. This tool only performs a Graph file
    download and writes a copy into the managed ADK landing-zone bucket.

    Args:
        request: IngestDriveItemRequest -> Drive item and hidden agent context.

    Returns:
        IngestDriveItemResponse -> GCS URI and inject_file_data flag.
    """
    logger.info("Tool call: ingest_sharepoint_drive_item(item_id={})", request.item_id)
    try:
        client = create_sharepoint_client()
        return await asyncio.to_thread(client.copy_file_to_landing_zone, request)
    except Exception as exc:
        return IngestDriveItemResponse(
            drive_id=request.drive_id,
            item_id=request.item_id,
            file=None,
            gcs_uri=None,
            mime_type="application/octet-stream",
            inject_file_data=False,
            execution_status="error",
            execution_message=_format_execution_error(exc),
        )


def _format_execution_error(exc: Exception) -> str:
    """Returns a sanitized user-facing tool error message."""
    raw_message = _sanitize_sensitive_text(str(exc))
    lowered = raw_message.lower()
    if any(
        marker in lowered
        for marker in (
            "access denied",
            "forbidden",
            "insufficient privileges",
            "permission denied",
            "unauthorized",
            "401",
            "403",
        )
    ):
        return f"Permission Denied: {raw_message}"
    if any(marker in lowered for marker in ("not found", "404")):
        return f"Object not found: {raw_message}"
    return raw_message


def _sanitize_sensitive_text(value: str) -> str:
    """Redacts common credential fragments from error messages."""
    sanitized = value or ""
    sanitized = re.sub(
        r"Bearer\s+[A-Za-z0-9._\-~+/]+=*",
        "Bearer [REDACTED]",
        sanitized,
    )
    sanitized = re.sub(r"access_token=[^&\s]+", "access_token=[REDACTED]", sanitized)
    return sanitized
