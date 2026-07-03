from __future__ import annotations

import asyncio
import html
import re
import time
from typing import Literal, Optional

import httpx
from loguru import logger
from pydantic import SecretStr

from .config import SHAREPOINT_SERVER_CONFIG
from .gcs_connector import GCSConnector
from .schemas import (
    DEFAULT_PAGE_SIZE,
    DiscoverSharePointSiteContentRequest,
    DiscoverSharePointSiteContentResponse,
    DriveItemMetadata,
    DriveMetadata,
    GetSharePointDriveItemRequest,
    GetSharePointDriveItemResponse,
    GetSharePointSitePageRequest,
    GetSharePointSitePageResponse,
    GetSharePointSiteRequest,
    GetSharePointSiteResponse,
    IngestSharePointDriveItemRequest,
    IngestSharePointDriveItemResponse,
    JsonObject,
    ListItemPreview,
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
    PageMetadata,
    SearchSharePointDriveItemsRequest,
    SearchSharePointDriveItemsResponse,
    SearchSharePointSitesRequest,
    SearchSharePointSitesResponse,
    SharePointListMetadata,
    SiteMetadata,
)


class StreamIOWrapper:
    """Wraps a synchronous httpx byte iterator into a file-like object."""

    def __init__(self, httpx_response: httpx.Response) -> None:
        """
        Initializes the wrapper around an active HTTP response stream.

        Args:
            httpx_response: httpx.Response -> The active streaming response.

        Returns:
            None -> Initializes the wrapper.
        """
        self.iterator = httpx_response.iter_bytes()
        self.buffer = b""
        self.position = 0

    def read(self, size: int = -1) -> bytes:
        """
        Reads bytes from the active HTTP stream.

        Args:
            size: int -> The number of bytes to read, or -1 for the rest.

        Returns:
            bytes -> The bytes read from the active stream.
        """
        if size == -1:
            payload = self.buffer + b"".join(self.iterator)
            self.buffer = b""
            self.position += len(payload)
            return payload

        while len(self.buffer) < size:
            try:
                self.buffer += next(self.iterator)
            except StopIteration:
                break

        payload = self.buffer[:size]
        self.buffer = self.buffer[size:]
        self.position += len(payload)
        return payload

    def tell(self) -> int:
        """
        Reports the current byte offset in the stream.

        Args:
            None

        Returns:
            int -> The current stream position.
        """
        return self.position


class SharePointClient:
    """Client for interacting with SharePoint through Microsoft Graph."""

    _collection_cache: dict[tuple[str, int], tuple[float, list[JsonObject]]] = {}
    _file_cache: dict[
        tuple[str, str, int], tuple[float, IngestSharePointDriveItemResponse]
    ] = {}
    _cache_ttl = SHAREPOINT_SERVER_CONFIG.cache_ttl_seconds

    def __init__(self, access_token: SecretStr) -> None:
        """
        Initializes the client with a delegated Microsoft access token.

        Args:
            access_token: SecretStr -> The Microsoft Graph delegated access token.

        Returns:
            None -> Initializes the SharePoint client.
        """
        if not access_token or not access_token.get_secret_value():
            raise ValueError("No access token provided for SharePointClient.")

        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {self.access_token.get_secret_value()}",
            "Accept": "application/json",
        }
        self.gcs_connector = GCSConnector()

    @classmethod
    def _sweep_cache(cls) -> None:
        """
        Removes expired cache entries to keep Cloud Run memory bounded.

        Args:
            None

        Returns:
            None -> Mutates the class-level caches.
        """
        current_time = time.time()
        for cache_dict in [cls._collection_cache, cls._file_cache]:
            expired_keys = [
                key
                for key, (cached_time, _) in cache_dict.items()
                if current_time - cached_time >= cls._cache_ttl
            ]
            for key in expired_keys:
                cache_dict.pop(key, None)

    async def _get(self, endpoint: str) -> JsonObject:
        """
        Performs an asynchronous GET request to Microsoft Graph.

        Args:
            endpoint: str -> Relative Graph endpoint or absolute nextLink URL.

        Returns:
            JsonObject -> The decoded JSON response payload.
        """
        url = endpoint
        if not endpoint.startswith("https://"):
            url = f"{SHAREPOINT_SERVER_CONFIG.graph_api_base_url}{endpoint}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, timeout=30.0)

        if response.status_code == 401:
            raise ValueError("Invalid or expired Microsoft access token.")

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Graph API request failed: %s", exc.response.text)
            raise RuntimeError(
                f"Graph API request failed: {response.status_code} - {response.text}"
            ) from exc
        return response.json()

    async def _fetch_collection(
        self, endpoint: str, use_cache: bool
    ) -> list[JsonObject]:
        """
        Fetches a full paginated Graph collection and hides nextLink from the LLM.

        Args:
            endpoint: str -> The first Microsoft Graph collection endpoint.
            use_cache: bool -> Whether to use the short-lived in-memory cache.

        Returns:
            list[JsonObject] -> All fetched collection entries.
        """
        token_hash = hash(self.access_token.get_secret_value())
        cache_key = (endpoint, token_hash)
        current_time = time.time()
        cached = self._collection_cache.get(cache_key)
        if use_cache and cached and current_time - cached[0] < self._cache_ttl:
            return cached[1]

        items: list[JsonObject] = []
        next_endpoint: Optional[str] = endpoint
        while next_endpoint:
            payload = await self._get(next_endpoint)
            raw_items = payload.get("value", [])
            if isinstance(raw_items, list):
                items.extend(
                    raw_item for raw_item in raw_items if isinstance(raw_item, dict)
                )
            next_link = payload.get("@odata.nextLink")
            next_endpoint = next_link if isinstance(next_link, str) else None

        self._sweep_cache()
        self._collection_cache[cache_key] = (current_time, items)
        return items

    def _slice_page(self, items: list[object], page: int) -> tuple[list[object], int]:
        """
        Slices a list with the configured LLM-friendly page size.

        Args:
            items: list[object] -> The full result list to slice.
            page: int -> The 1-indexed page number requested.

        Returns:
            tuple[list[object], int] -> The page items and total page count.
        """
        total_pages = max(1, (len(items) + DEFAULT_PAGE_SIZE - 1) // DEFAULT_PAGE_SIZE)
        start_index = (page - 1) * DEFAULT_PAGE_SIZE
        end_index = start_index + DEFAULT_PAGE_SIZE
        return items[start_index:end_index], total_pages

    def _format_site(self, raw_site: JsonObject) -> SiteMetadata:
        """
        Converts a raw Graph site payload into normalized site metadata.

        Args:
            raw_site: JsonObject -> Raw site payload from Microsoft Graph.

        Returns:
            SiteMetadata -> Normalized site metadata.
        """
        sharepoint_ids = raw_site.get("sharepointIds")
        return SiteMetadata(
            site_id=str(raw_site.get("id", "")),
            name=self._optional_str(raw_site.get("name")),
            display_name=self._optional_str(raw_site.get("displayName")),
            description=self._optional_str(raw_site.get("description")),
            web_url=self._optional_str(raw_site.get("webUrl")),
            hostname=self._optional_str(raw_site.get("hostname")),
            created_date_time=self._optional_str(raw_site.get("createdDateTime")),
            last_modified_date_time=self._optional_str(
                raw_site.get("lastModifiedDateTime")
            ),
            sharepoint_ids=sharepoint_ids if isinstance(sharepoint_ids, dict) else None,
        )

    def _format_drive(self, raw_drive: JsonObject) -> DriveMetadata:
        """
        Converts a raw Graph drive payload into normalized drive metadata.

        Args:
            raw_drive: JsonObject -> Raw drive payload from Microsoft Graph.

        Returns:
            DriveMetadata -> Normalized drive metadata.
        """
        return DriveMetadata(
            drive_id=str(raw_drive.get("id", "")),
            name=self._optional_str(raw_drive.get("name")),
            description=self._optional_str(raw_drive.get("description")),
            drive_type=self._optional_str(raw_drive.get("driveType")),
            web_url=self._optional_str(raw_drive.get("webUrl")),
            created_date_time=self._optional_str(raw_drive.get("createdDateTime")),
            last_modified_date_time=self._optional_str(
                raw_drive.get("lastModifiedDateTime")
            ),
        )

    def _format_list(self, raw_list: JsonObject) -> SharePointListMetadata:
        """
        Converts a raw Graph list payload into normalized list metadata.

        Args:
            raw_list: JsonObject -> Raw list payload from Microsoft Graph.

        Returns:
            SharePointListMetadata -> Normalized list metadata.
        """
        list_info = raw_list.get("list")
        template = None
        if isinstance(list_info, dict):
            template = self._optional_str(list_info.get("template"))
        return SharePointListMetadata(
            list_id=str(raw_list.get("id", "")),
            name=self._optional_str(raw_list.get("name")),
            display_name=self._optional_str(raw_list.get("displayName")),
            template=template,
            web_url=self._optional_str(raw_list.get("webUrl")),
            created_date_time=self._optional_str(raw_list.get("createdDateTime")),
            last_modified_date_time=self._optional_str(
                raw_list.get("lastModifiedDateTime")
            ),
        )

    def _format_page(self, raw_page: JsonObject) -> PageMetadata:
        """
        Converts a raw Graph sitePage payload into normalized page metadata.

        Args:
            raw_page: JsonObject -> Raw page payload from Microsoft Graph.

        Returns:
            PageMetadata -> Normalized page metadata.
        """
        return PageMetadata(
            page_id=str(raw_page.get("id", "")),
            title=self._optional_str(raw_page.get("title")),
            name=self._optional_str(raw_page.get("name")),
            page_layout=self._optional_str(raw_page.get("pageLayout")),
            promotion_kind=self._optional_str(raw_page.get("promotionKind")),
            web_url=self._optional_str(raw_page.get("webUrl")),
            created_date_time=self._optional_str(raw_page.get("createdDateTime")),
            last_modified_date_time=self._optional_str(
                raw_page.get("lastModifiedDateTime")
            ),
        )

    def _format_drive_item(self, raw_item: JsonObject) -> DriveItemMetadata:
        """
        Converts a raw Graph driveItem payload into normalized item metadata.

        Args:
            raw_item: JsonObject -> Raw driveItem payload from Microsoft Graph.

        Returns:
            DriveItemMetadata -> Normalized drive item metadata.
        """
        folder_info = raw_item.get("folder")
        file_info = raw_item.get("file")
        item_type = self._drive_item_type(raw_item)
        return DriveItemMetadata(
            item_id=str(raw_item.get("id", "")),
            name=self._optional_str(raw_item.get("name")),
            item_type=item_type,
            web_url=self._optional_str(raw_item.get("webUrl")),
            mime_type=self._extract_mime_type(file_info),
            size=self._optional_int(raw_item.get("size")),
            child_count=self._extract_child_count(folder_info),
            parent_reference=self._optional_dict(raw_item.get("parentReference")),
            created_date_time=self._optional_str(raw_item.get("createdDateTime")),
            last_modified_date_time=self._optional_str(
                raw_item.get("lastModifiedDateTime")
            ),
            created_by=self._extract_user(raw_item.get("createdBy")),
            last_modified_by=self._extract_user(raw_item.get("lastModifiedBy")),
        )

    def _format_list_item(self, raw_item: JsonObject) -> ListItemPreview:
        """
        Converts a raw listItem payload into visible fields and preview text.

        Args:
            raw_item: JsonObject -> Raw listItem payload from Microsoft Graph.

        Returns:
            ListItemPreview -> Normalized list item preview.
        """
        fields = self._optional_dict(raw_item.get("fields")) or {}
        visible_fields = {
            key: value
            for key, value in fields.items()
            if not key.startswith("@") and value is not None
        }
        return ListItemPreview(
            item_id=str(raw_item.get("id", "")),
            web_url=self._optional_str(raw_item.get("webUrl")),
            created_date_time=self._optional_str(raw_item.get("createdDateTime")),
            last_modified_date_time=self._optional_str(
                raw_item.get("lastModifiedDateTime")
            ),
            fields=visible_fields,
            text_preview=self._build_field_preview(visible_fields),
        )

    def _build_field_preview(self, fields: JsonObject) -> str:
        """
        Builds a compact preview string from visible SharePoint list fields.

        Args:
            fields: JsonObject -> Visible field values from a SharePoint list item.

        Returns:
            str -> A compact human-readable preview.
        """
        preview_parts = []
        for key, value in fields.items():
            if (
                len(preview_parts)
                >= SHAREPOINT_SERVER_CONFIG.max_list_item_preview_fields
            ):
                break
            if isinstance(value, (dict, list)) or value is None:
                continue
            preview_parts.append(f"{key}: {value}")
        return " | ".join(preview_parts)

    def _extract_page_text(self, payload: JsonObject) -> str:
        """
        Extracts useful readable text from the expanded modern page payload.

        Args:
            payload: JsonObject -> Expanded Microsoft Graph sitePage payload.

        Returns:
            str -> Deduplicated, cleaned text suitable for the agent.
        """
        text_chunks: list[str] = []
        self._walk_text_payload(payload, "", text_chunks)
        deduped_chunks = list(dict.fromkeys(chunk for chunk in text_chunks if chunk))
        joined_text = "\n".join(deduped_chunks)
        return joined_text[: SHAREPOINT_SERVER_CONFIG.max_page_text_chars]

    def _walk_text_payload(
        self,
        node: object,
        parent_key: str,
        text_chunks: list[str],
    ) -> None:
        """
        Recursively walks a Graph page payload and captures readable text fields.

        Args:
            node: object -> Current JSON node being inspected.
            parent_key: str -> Parent JSON key for text-field heuristics.
            text_chunks: list[str] -> Mutable list of captured text chunks.

        Returns:
            None -> Appends cleaned text chunks in place.
        """
        if isinstance(node, dict):
            for key, value in node.items():
                if self._is_technical_key(key):
                    continue
                self._walk_text_payload(value, key, text_chunks)
            return
        if isinstance(node, list):
            for item in node:
                self._walk_text_payload(item, parent_key, text_chunks)
            return
        if isinstance(node, str) and self._is_readable_text_key(parent_key):
            cleaned_text = self._clean_text(node)
            if cleaned_text:
                text_chunks.append(cleaned_text)

    async def search_sharepoint_sites(
        self, request: SearchSharePointSitesRequest
    ) -> SearchSharePointSitesResponse:
        """
        Searches SharePoint sites visible to the signed-in Microsoft user.

        Args:
            request: SearchSharePointSitesRequest -> Site query and pagination settings.

        Returns:
            SearchSharePointSitesResponse -> Matching SharePoint sites.
        """
        raw_sites = await self._fetch_collection(request.endpoint, request.use_cache)
        sites = [self._format_site(raw_site) for raw_site in raw_sites]
        page_items, total_pages = self._slice_page(sites, request.page)
        return SearchSharePointSitesResponse(
            total_items=len(sites),
            total_pages=total_pages,
            current_page=request.page,
            items_in_page=len(page_items),
            sites=page_items,
        )

    async def get_sharepoint_site(
        self, request: GetSharePointSiteRequest
    ) -> GetSharePointSiteResponse:
        """
        Reads expanded metadata for one SharePoint site.

        Args:
            request: GetSharePointSiteRequest -> The target SharePoint site ID.

        Returns:
            GetSharePointSiteResponse -> The normalized site metadata.
        """
        raw_site = await self._get(request.endpoint)
        return GetSharePointSiteResponse(site=self._format_site(raw_site))

    async def discover_sharepoint_site_content(
        self, request: DiscoverSharePointSiteContentRequest
    ) -> DiscoverSharePointSiteContentResponse:
        """
        Discovers site metadata, document libraries, lists, and modern pages.

        Args:
            request: DiscoverSharePointSiteContentRequest -> Site ID and include flags.

        Returns:
            DiscoverSharePointSiteContentResponse -> Site content overview.
        """
        site_request = GetSharePointSiteRequest(site_id=request.site_id)
        site = (await self.get_sharepoint_site(site_request)).site

        drives, lists, pages = await asyncio.gather(
            self._discover_drives(request),
            self._discover_lists(request),
            self._discover_pages(request),
        )
        return DiscoverSharePointSiteContentResponse(
            site=site,
            document_libraries=drives,
            lists=lists,
            pages=pages,
        )

    async def list_sharepoint_site_drives(
        self, request: ListSharePointSiteDrivesRequest
    ) -> ListSharePointSiteDrivesResponse:
        """
        Lists SharePoint document-library drives available inside a site.

        Args:
            request: ListSharePointSiteDrivesRequest -> Site ID and pagination settings.

        Returns:
            ListSharePointSiteDrivesResponse -> Document-library drives.
        """
        raw_drives = await self._fetch_collection(request.endpoint, request.use_cache)
        drives = [self._format_drive(raw_drive) for raw_drive in raw_drives]
        page_items, total_pages = self._slice_page(drives, request.page)
        return ListSharePointSiteDrivesResponse(
            total_items=len(drives),
            total_pages=total_pages,
            current_page=request.page,
            items_in_page=len(page_items),
            drives=page_items,
        )

    async def list_sharepoint_site_lists(
        self, request: ListSharePointSiteListsRequest
    ) -> ListSharePointSiteListsResponse:
        """
        Lists SharePoint lists inside a site.

        Args:
            request: ListSharePointSiteListsRequest -> Site ID and pagination settings.

        Returns:
            ListSharePointSiteListsResponse -> SharePoint lists.
        """
        raw_lists = await self._fetch_collection(request.endpoint, request.use_cache)
        lists = [self._format_list(raw_list) for raw_list in raw_lists]
        page_items, total_pages = self._slice_page(lists, request.page)
        return ListSharePointSiteListsResponse(
            total_items=len(lists),
            total_pages=total_pages,
            current_page=request.page,
            items_in_page=len(page_items),
            lists=page_items,
        )

    async def list_sharepoint_list_items(
        self, request: ListSharePointListItemsRequest
    ) -> ListSharePointListItemsResponse:
        """
        Reads visible field values from a SharePoint list.

        Args:
            request: ListSharePointListItemsRequest -> Site and list identifiers.

        Returns:
            ListSharePointListItemsResponse -> List items with previews.
        """
        raw_items = await self._fetch_collection(request.endpoint, request.use_cache)
        items = [self._format_list_item(raw_item) for raw_item in raw_items]
        page_items, total_pages = self._slice_page(items, request.page)
        return ListSharePointListItemsResponse(
            total_items=len(items),
            total_pages=total_pages,
            current_page=request.page,
            items_in_page=len(page_items),
            items=page_items,
        )

    async def list_sharepoint_site_pages(
        self, request: ListSharePointSitePagesRequest
    ) -> ListSharePointSitePagesResponse:
        """
        Lists modern SharePoint pages in a site.

        Args:
            request: ListSharePointSitePagesRequest -> Site ID and pagination settings.

        Returns:
            ListSharePointSitePagesResponse -> Modern SharePoint pages.
        """
        raw_pages = await self._fetch_collection(request.endpoint, request.use_cache)
        pages = [self._format_page(raw_page) for raw_page in raw_pages]
        page_items, total_pages = self._slice_page(pages, request.page)
        return ListSharePointSitePagesResponse(
            total_items=len(pages),
            total_pages=total_pages,
            current_page=request.page,
            items_in_page=len(page_items),
            pages=page_items,
        )

    async def get_sharepoint_site_page(
        self, request: GetSharePointSitePageRequest
    ) -> GetSharePointSitePageResponse:
        """
        Reads a modern SharePoint page and extracts readable text.

        Args:
            request: GetSharePointSitePageRequest -> Site and page identifiers.

        Returns:
            GetSharePointSitePageResponse -> Page metadata and extracted text.
        """
        raw_page = await self._get(request.endpoint)
        page_text = self._extract_page_text(raw_page)
        return GetSharePointSitePageResponse(
            page=self._format_page(raw_page),
            text=page_text,
            text_char_count=len(page_text),
        )

    async def list_sharepoint_drive_items(
        self, request: ListSharePointDriveItemsRequest
    ) -> ListSharePointDriveItemsResponse:
        """
        Lists files and folders from a SharePoint document-library drive.

        Args:
            request: ListSharePointDriveItemsRequest -> Drive ID and optional folder location.

        Returns:
            ListSharePointDriveItemsResponse -> Files and folders in the location.
        """
        raw_items = await self._fetch_collection(request.endpoint, request.use_cache)
        items = [self._format_drive_item(raw_item) for raw_item in raw_items]
        page_items, total_pages = self._slice_page(items, request.page)
        return ListSharePointDriveItemsResponse(
            total_items=len(items),
            total_pages=total_pages,
            current_page=request.page,
            items_in_page=len(page_items),
            items=page_items,
        )

    async def get_sharepoint_drive_item(
        self, request: GetSharePointDriveItemRequest
    ) -> GetSharePointDriveItemResponse:
        """
        Reads metadata for a single SharePoint drive item.

        Args:
            request: GetSharePointDriveItemRequest -> Drive and item identifiers.

        Returns:
            GetSharePointDriveItemResponse -> Normalized drive item metadata.
        """
        raw_item = await self._get(request.endpoint)
        return GetSharePointDriveItemResponse(item=self._format_drive_item(raw_item))

    async def search_sharepoint_drive_items(
        self, request: SearchSharePointDriveItemsRequest
    ) -> SearchSharePointDriveItemsResponse:
        """
        Searches files and folders inside a SharePoint document-library drive.

        Args:
            request: SearchSharePointDriveItemsRequest -> Drive ID and search query.

        Returns:
            SearchSharePointDriveItemsResponse -> Matching drive items.
        """
        raw_items = await self._fetch_collection(request.endpoint, request.use_cache)
        items = [self._format_drive_item(raw_item) for raw_item in raw_items]
        page_items, total_pages = self._slice_page(items, request.page)
        return SearchSharePointDriveItemsResponse(
            total_items=len(items),
            total_pages=total_pages,
            current_page=request.page,
            items_in_page=len(page_items),
            items=page_items,
        )

    async def ingest_sharepoint_drive_item(
        self, request: IngestSharePointDriveItemRequest
    ) -> IngestSharePointDriveItemResponse:
        """
        Downloads one SharePoint file and copies it into the GCS Landing Zone.

        Args:
            request: IngestSharePointDriveItemRequest -> Drive/item IDs and context.

        Returns:
            IngestSharePointDriveItemResponse -> GCS URI and injection metadata.
        """
        if not request.dependencies:
            raise ValueError("SessionContext must be provided to ingest files.")

        cache_key = (
            request.drive_id,
            request.item_id,
            hash(self.access_token.get_secret_value()),
        )
        cached = self._file_cache.get(cache_key)
        if request.use_cache and cached and time.time() - cached[0] < self._cache_ttl:
            return cached[1]

        metadata = await self._get(request.metadata_endpoint)
        if "folder" in metadata or "package" in metadata:
            raise ValueError(
                "Only file drive items can be ingested into the landing zone."
            )

        filename = (
            self._optional_str(metadata.get("name")) or f"sharepoint-{request.item_id}"
        )
        file_info = metadata.get("file")
        mime_type = self._extract_mime_type(file_info) or "application/octet-stream"
        file_size = self._optional_int(metadata.get("size"))

        gcs_uri = await asyncio.to_thread(
            self._stream_to_landing_zone,
            request.content_endpoint,
            mime_type,
            filename,
            file_size,
            request.dependencies.app_name,
            request.dependencies.user_id,
            request.dependencies.session_id,
        )
        response = IngestSharePointDriveItemResponse(
            gcs_uri=gcs_uri,
            mime_type=mime_type,
            filename=filename,
            inject_file_data=True,
        )
        self._sweep_cache()
        self._file_cache[cache_key] = (time.time(), response)
        return response

    async def _discover_drives(
        self, request: DiscoverSharePointSiteContentRequest
    ) -> list[DriveMetadata]:
        """
        Discovers document-library drives when requested.

        Args:
            request: DiscoverSharePointSiteContentRequest -> Discovery settings.

        Returns:
            list[DriveMetadata] -> Discovered drives or an empty list.
        """
        if not request.include_document_libraries:
            return []
        list_request = ListSharePointSiteDrivesRequest(
            site_id=request.site_id,
            use_cache=request.use_cache,
        )
        return (await self.list_sharepoint_site_drives(list_request)).drives

    async def _discover_lists(
        self, request: DiscoverSharePointSiteContentRequest
    ) -> list[SharePointListMetadata]:
        """
        Discovers SharePoint lists when requested.

        Args:
            request: DiscoverSharePointSiteContentRequest -> Discovery settings.

        Returns:
            list[SharePointListMetadata] -> Discovered lists or an empty list.
        """
        if not request.include_lists:
            return []
        list_request = ListSharePointSiteListsRequest(
            site_id=request.site_id,
            use_cache=request.use_cache,
        )
        return (await self.list_sharepoint_site_lists(list_request)).lists

    async def _discover_pages(
        self, request: DiscoverSharePointSiteContentRequest
    ) -> list[PageMetadata]:
        """
        Discovers modern SharePoint pages when requested.

        Args:
            request: DiscoverSharePointSiteContentRequest -> Discovery settings.

        Returns:
            list[PageMetadata] -> Discovered pages or an empty list.
        """
        if not request.include_pages:
            return []
        pages_request = ListSharePointSitePagesRequest(
            site_id=request.site_id,
            use_cache=request.use_cache,
        )
        return (await self.list_sharepoint_site_pages(pages_request)).pages

    def _stream_to_landing_zone(
        self,
        content_endpoint: str,
        mime_type: str,
        filename: str,
        file_size: Optional[int],
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> str:
        """
        Streams a SharePoint file directly into the GCS Landing Zone.

        Args:
            content_endpoint: str -> Relative Graph content endpoint for the file.
            mime_type: str -> File MIME type.
            filename: str -> Original SharePoint filename.
            file_size: Optional[int] -> File size in bytes, when provided.
            app_name: str -> Calling app name.
            user_id: str -> Calling user ID.
            session_id: str -> Calling session ID.

        Returns:
            str -> The resulting GCS URI.
        """
        url = f"{SHAREPOINT_SERVER_CONFIG.graph_api_base_url}{content_endpoint}"
        with httpx.Client() as client:
            with client.stream(
                "GET",
                url,
                headers=self.headers,
                follow_redirects=True,
                timeout=60.0,
            ) as response:
                if response.status_code == 401:
                    raise ValueError("Invalid or expired Microsoft access token.")
                response.raise_for_status()
                return self.gcs_connector.upload_stream(
                    file_obj=StreamIOWrapper(response),
                    content_type=mime_type,
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename,
                    size=file_size,
                )

    def _drive_item_type(
        self, raw_item: JsonObject
    ) -> Literal["file", "folder", "package", "unknown"]:
        """
        Determines the normalized type for a Graph driveItem payload.

        Args:
            raw_item: JsonObject -> Raw driveItem payload.

        Returns:
            Literal["file", "folder", "package", "unknown"] -> The normalized type.
        """
        if "folder" in raw_item:
            return "folder"
        if "file" in raw_item:
            return "file"
        if "package" in raw_item:
            return "package"
        return "unknown"

    def _extract_mime_type(self, file_info: object) -> Optional[str]:
        """
        Extracts a MIME type from a Graph file facet.

        Args:
            file_info: object -> Raw file facet payload.

        Returns:
            Optional[str] -> The MIME type, when present.
        """
        if isinstance(file_info, dict):
            return self._optional_str(file_info.get("mimeType"))
        return None

    def _extract_child_count(self, folder_info: object) -> Optional[int]:
        """
        Extracts the child count from a Graph folder facet.

        Args:
            folder_info: object -> Raw folder facet payload.

        Returns:
            Optional[int] -> The child count, when present.
        """
        if isinstance(folder_info, dict):
            return self._optional_int(folder_info.get("childCount"))
        return None

    def _extract_user(self, user_container: object) -> Optional[str]:
        """
        Extracts a user display name or email from Graph identity metadata.

        Args:
            user_container: object -> Raw Graph identity-set payload.

        Returns:
            Optional[str] -> User display name, email, or ID.
        """
        if not isinstance(user_container, dict):
            return None
        user_info = user_container.get("user")
        if not isinstance(user_info, dict):
            return None
        return (
            self._optional_str(user_info.get("displayName"))
            or self._optional_str(user_info.get("email"))
            or self._optional_str(user_info.get("id"))
        )

    def _optional_str(self, value: object) -> Optional[str]:
        """
        Converts values to a non-empty string when possible.

        Args:
            value: object -> Raw value to normalize.

        Returns:
            Optional[str] -> A non-empty string or None.
        """
        if value is None:
            return None
        string_value = str(value).strip()
        return string_value or None

    def _optional_int(self, value: object) -> Optional[int]:
        """
        Converts values to an int when possible.

        Args:
            value: object -> Raw value to normalize.

        Returns:
            Optional[int] -> An integer or None.
        """
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _optional_dict(self, value: object) -> Optional[JsonObject]:
        """
        Returns a dictionary only when the raw value is a dictionary.

        Args:
            value: object -> Raw value to inspect.

        Returns:
            Optional[JsonObject] -> The value as a dictionary or None.
        """
        return value if isinstance(value, dict) else None

    def _is_technical_key(self, key: str) -> bool:
        """
        Identifies technical JSON keys that should not contribute readable text.

        Args:
            key: str -> JSON key to inspect.

        Returns:
            bool -> True when the key is technical metadata.
        """
        lowered_key = key.lower()
        technical_tokens = ("id", "url", "etag", "date", "thumbnail", "@odata")
        return any(token in lowered_key for token in technical_tokens)

    def _is_readable_text_key(self, key: str) -> bool:
        """
        Identifies page payload keys that usually contain human-readable content.

        Args:
            key: str -> JSON key to inspect.

        Returns:
            bool -> True when string values under this key should be captured.
        """
        lowered_key = key.lower()
        readable_tokens = (
            "title",
            "description",
            "text",
            "html",
            "caption",
            "alt",
            "header",
            "displayname",
            "webpartdata",
        )
        return any(token in lowered_key for token in readable_tokens)

    def _clean_text(self, value: str) -> str:
        """
        Converts HTML-rich strings into compact plain text.

        Args:
            value: str -> Raw text or HTML value.

        Returns:
            str -> Cleaned readable text.
        """
        decoded = html.unescape(value)
        without_tags = re.sub(r"<[^>]+>", " ", decoded)
        normalized = re.sub(r"\s+", " ", without_tags).strip()
        if normalized.startswith("{") or normalized.startswith("["):
            return ""
        return normalized
