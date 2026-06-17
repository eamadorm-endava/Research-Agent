from __future__ import annotations

import datetime
import html
import re
from collections.abc import Mapping, Sequence
from typing import Any, Optional, cast
from urllib.parse import quote

import google.auth
import httpx
from google.cloud import storage
from loguru import logger

from .config import SHAREPOINT_API_CONFIG, SHAREPOINT_LANDING_ZONE_CONFIG
from .schemas import (
    IngestDriveItemRequest,
    IngestDriveItemResponse,
    SharePointDrive,
    SharePointDriveItem,
    SharePointFileMetadata,
    SharePointItemKind,
    SharePointListItem,
    SharePointListResource,
    SharePointPageContent,
    SharePointPageSummary,
    SharePointSite,
    SharePointSiteContentOverview,
    SharePointSiteDetail,
)


class SharePointClient:
    """Read-only Microsoft Graph client for SharePoint sites and content."""

    def __init__(self, access_token: str) -> None:
        """Creates a Microsoft Graph client with delegated bearer authentication.

        Args:
            access_token: str -> Delegated Microsoft Graph OAuth access token.

        Returns:
            None -> The initialized client stores HTTP configuration for later calls.
        """
        self.access_token = access_token
        self.http_client = httpx.Client(
            timeout=SHAREPOINT_API_CONFIG.request_timeout_seconds,
            follow_redirects=True,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )

    def search_sites(self, query: str, max_results: int) -> list[SharePointSite]:
        """Searches SharePoint sites visible to the signed-in user.

        Args:
            query: str -> Site search text.
            max_results: int -> Maximum number of sites to return.

        Returns:
            list[SharePointSite] -> Matching SharePoint site metadata.
        """
        logger.info("Searching SharePoint sites with query='{}'", query)
        payloads = self._paginated_get(
            "/sites",
            params={
                "search": query,
                "$top": str(min(max_results, SHAREPOINT_API_CONFIG.page_size)),
                "$select": _site_select_fields(),
            },
            max_results=max_results,
        )
        return [self._build_site(payload) for payload in payloads]

    def get_site(self, site_id: str) -> SharePointSiteDetail:
        """Reads expanded metadata for a SharePoint site.

        Args:
            site_id: str -> Microsoft Graph site ID.

        Returns:
            SharePointSiteDetail -> Expanded site metadata.
        """
        logger.info("Getting SharePoint site '{}'", site_id)
        site_segment = _quote_graph_segment(site_id)
        payload = self._get_single(
            f"/sites/{site_segment}",
            params={"$select": _site_detail_select_fields()},
        )
        return self._build_site_detail(payload)

    def discover_site_content(
        self, site_id: str, max_results: int
    ) -> SharePointSiteContentOverview:
        """Returns high-level site metadata, libraries, lists, and pages.

        Args:
            site_id: str -> Microsoft Graph site ID.
            max_results: int -> Maximum number of each content container to return.

        Returns:
            SharePointSiteContentOverview -> Site-level content inventory.
        """
        return SharePointSiteContentOverview(
            site=self.get_site(site_id),
            drives=self.list_site_drives(site_id=site_id, max_results=max_results),
            lists=self.list_site_lists(site_id=site_id, max_results=max_results),
            pages=self.list_site_pages(site_id=site_id, max_results=max_results),
        )

    def list_site_drives(self, site_id: str, max_results: int) -> list[SharePointDrive]:
        """Lists document-library drives for a SharePoint site.

        Args:
            site_id: str -> Microsoft Graph site ID.
            max_results: int -> Maximum number of drives to return.

        Returns:
            list[SharePointDrive] -> Document libraries in the site.
        """
        logger.info("Listing SharePoint drives for site_id='{}'", site_id)
        site_segment = _quote_graph_segment(site_id)
        payloads = self._paginated_get(
            f"/sites/{site_segment}/drives",
            params={
                "$top": str(min(max_results, SHAREPOINT_API_CONFIG.page_size)),
                "$select": "id,name,driveType,webUrl,createdDateTime,lastModifiedDateTime",
            },
            max_results=max_results,
        )
        return [self._build_drive(payload) for payload in payloads]

    def list_site_lists(
        self, site_id: str, max_results: int
    ) -> list[SharePointListResource]:
        """Lists SharePoint lists inside a site.

        Args:
            site_id: str -> Microsoft Graph site ID.
            max_results: int -> Maximum number of lists to return.

        Returns:
            list[SharePointListResource] -> SharePoint lists in the site.
        """
        logger.info("Listing SharePoint lists for site_id='{}'", site_id)
        site_segment = _quote_graph_segment(site_id)
        payloads = self._paginated_get(
            f"/sites/{site_segment}/lists",
            params={
                "$top": str(min(max_results, SHAREPOINT_API_CONFIG.page_size)),
                "$select": "id,name,displayName,webUrl,list,createdDateTime,lastModifiedDateTime",
            },
            max_results=max_results,
        )
        return [self._build_list_resource(payload) for payload in payloads]

    def list_list_items(
        self, site_id: str, list_id: str, max_results: int
    ) -> list[SharePointListItem]:
        """Lists field values for items in one SharePoint list.

        Args:
            site_id: str -> Microsoft Graph site ID.
            list_id: str -> Microsoft Graph list ID.
            max_results: int -> Maximum number of list items to return.

        Returns:
            list[SharePointListItem] -> List item records with visible fields.
        """
        logger.info("Listing SharePoint list items for list_id='{}'", list_id)
        site_segment = _quote_graph_segment(site_id)
        list_segment = _quote_graph_segment(list_id)
        payloads = self._paginated_get(
            f"/sites/{site_segment}/lists/{list_segment}/items",
            params={
                "$top": str(min(max_results, SHAREPOINT_API_CONFIG.page_size)),
                "$select": "id,webUrl,createdDateTime,lastModifiedDateTime",
                "$expand": "fields",
            },
            max_results=max_results,
        )
        return [self._build_list_item(payload) for payload in payloads]

    def list_site_pages(
        self, site_id: str, max_results: int
    ) -> list[SharePointPageSummary]:
        """Lists modern SharePoint pages in a site.

        Args:
            site_id: str -> Microsoft Graph site ID.
            max_results: int -> Maximum number of pages to return.

        Returns:
            list[SharePointPageSummary] -> Site page metadata records.
        """
        logger.info("Listing SharePoint pages for site_id='{}'", site_id)
        site_segment = _quote_graph_segment(site_id)
        payloads = self._paginated_get(
            f"/sites/{site_segment}/pages/microsoft.graph.sitePage",
            params={
                "$top": str(min(max_results, SHAREPOINT_API_CONFIG.page_size)),
                "$select": _page_select_fields(),
            },
            max_results=max_results,
        )
        return [self._build_page_summary(payload) for payload in payloads]

    def get_site_page(
        self, site_id: str, page_id: str, max_text_chars: int
    ) -> SharePointPageContent:
        """Reads a SharePoint site page and extracts answerable text.

        Args:
            site_id: str -> Microsoft Graph site ID.
            page_id: str -> Microsoft Graph sitePage ID.
            max_text_chars: int -> Maximum extracted text characters to return.

        Returns:
            SharePointPageContent -> Page metadata and extracted readable text.
        """
        logger.info("Getting SharePoint page '{}'", page_id)
        site_segment = _quote_graph_segment(site_id)
        page_segment = _quote_graph_segment(page_id)
        payload = self._get_single(
            f"/sites/{site_segment}/pages/{page_segment}/microsoft.graph.sitePage",
            params={
                "$select": _page_select_fields(),
                "$expand": "canvasLayout",
            },
        )
        return self._build_page_content(payload, max_text_chars=max_text_chars)

    def list_drive_items(
        self,
        *,
        drive_id: str,
        item_id: Optional[str],
        folder_path: Optional[str],
        max_results: int,
    ) -> list[SharePointDriveItem]:
        """Lists children in a SharePoint drive folder using root, item ID, or path.

        Args:
            drive_id: str -> Microsoft Graph drive ID.
            item_id: Optional[str] -> Optional folder driveItem ID.
            folder_path: Optional[str] -> Optional root-relative folder path.
            max_results: int -> Maximum number of child items to return.

        Returns:
            list[SharePointDriveItem] -> Child file and folder metadata.
        """
        logger.info("Listing SharePoint drive items for drive_id='{}'", drive_id)
        path = self._build_children_path(drive_id, item_id, folder_path)
        payloads = self._paginated_get(
            path,
            params={
                "$top": str(min(max_results, SHAREPOINT_API_CONFIG.page_size)),
                "$select": _drive_item_select_fields(),
            },
            max_results=max_results,
        )
        return [self._build_drive_item(payload) for payload in payloads]

    def get_drive_item(self, drive_id: str, item_id: str) -> SharePointDriveItem:
        """Reads metadata for a single SharePoint drive item.

        Args:
            drive_id: str -> Microsoft Graph drive ID.
            item_id: str -> Microsoft Graph driveItem ID.

        Returns:
            SharePointDriveItem -> File or folder metadata.
        """
        logger.info("Getting SharePoint drive item '{}'", item_id)
        drive_segment = _quote_graph_segment(drive_id)
        item_segment = _quote_graph_segment(item_id)
        payload = self._get_single(
            f"/drives/{drive_segment}/items/{item_segment}",
            params={"$select": _drive_item_select_fields()},
        )
        return self._build_drive_item(payload)

    def search_drive_items(
        self, drive_id: str, query: str, max_results: int
    ) -> list[SharePointDriveItem]:
        """Searches files and folders in a SharePoint document library drive.

        Args:
            drive_id: str -> Microsoft Graph drive ID.
            query: str -> Search text.
            max_results: int -> Maximum number of items to return.

        Returns:
            list[SharePointDriveItem] -> Matching drive item metadata.
        """
        logger.info("Searching SharePoint drive '{}' for query='{}'", drive_id, query)
        drive_segment = _quote_graph_segment(drive_id)
        encoded_query = quote(query.replace("'", "''"), safe="")
        payloads = self._paginated_get(
            f"/drives/{drive_segment}/root/search(q='{encoded_query}')",
            params={
                "$top": str(min(max_results, SHAREPOINT_API_CONFIG.page_size)),
                "$select": _drive_item_select_fields(),
            },
            max_results=max_results,
        )
        return [self._build_drive_item(payload) for payload in payloads]

    def copy_file_to_landing_zone(
        self, request: IngestDriveItemRequest
    ) -> IngestDriveItemResponse:
        """Copies one SharePoint file to the GCS landing zone without mutating SharePoint.

        Args:
            request: IngestDriveItemRequest -> Source item and hidden agent context.

        Returns:
            IngestDriveItemResponse -> GCS URI and metadata for multimodal injection.
        """
        dependencies = request.required_dependencies
        item = self.get_drive_item(request.drive_id, request.item_id)
        if item.kind != SharePointItemKind.FILE:
            raise ValueError(
                "Only SharePoint files can be copied into the landing zone."
            )

        filename = _sanitize_filename(request.filename or item.name)
        folder_prefix = f"{dependencies.app_name}/{dependencies.user_id}/"
        object_name = self._build_landing_zone_object_name(
            folder_prefix=folder_prefix,
            session_id=dependencies.session_id,
            filename=filename,
        )
        mime_type = item.mime_type or "application/octet-stream"

        self._stream_graph_file_to_gcs(
            drive_id=request.drive_id,
            item_id=request.item_id,
            destination_object_name=object_name,
            mime_type=mime_type,
            source_item=item,
            user_id=dependencies.user_id,
        )
        self._grant_landing_zone_read_access(folder_prefix, dependencies.user_id)

        gcs_uri = f"gs://{SHAREPOINT_LANDING_ZONE_CONFIG.bucket_name}/{object_name}"
        return IngestDriveItemResponse(
            drive_id=request.drive_id,
            item_id=request.item_id,
            file=SharePointFileMetadata.model_validate(item.model_dump()),
            gcs_uri=gcs_uri,
            mime_type=mime_type,
            inject_file_data=True,
            execution_status="success",
            execution_message=f"Successfully copied SharePoint file to {gcs_uri}.",
        )

    def _paginated_get(
        self,
        path_or_url: str,
        *,
        params: Optional[Mapping[str, str]] = None,
        max_results: int,
    ) -> list[dict[str, object]]:
        """Follows Microsoft Graph paging links until enough records are collected.

        Args:
            path_or_url: str -> Relative Graph path or absolute nextLink URL.
            params: Optional[Mapping[str, str]] -> Query parameters for the first request.
            max_results: int -> Maximum number of value payloads to collect.

        Returns:
            list[dict[str, object]] -> Raw Graph payloads from the value collection.
        """
        values: list[dict[str, object]] = []
        next_url: Optional[str] = path_or_url
        current_params = dict(params or {})
        page_count = 0

        while next_url and len(values) < max_results:
            page_count += 1
            if page_count > SHAREPOINT_API_CONFIG.max_pages:
                logger.warning("Stopping Graph pagination after configured page cap")
                break

            response = self.http_client.get(
                self._build_url(next_url), params=current_params
            )
            self._raise_for_status(response)
            payload = cast(dict[str, object], response.json())
            values.extend(_extract_mapping_list(payload.get("value")))
            next_url = _optional_str(payload.get("@odata.nextLink"))
            current_params = {}

        return values[:max_results]

    def _get_single(
        self, path_or_url: str, *, params: Optional[Mapping[str, str]] = None
    ) -> dict[str, object]:
        """Returns one Microsoft Graph JSON object.

        Args:
            path_or_url: str -> Relative Graph path or absolute URL.
            params: Optional[Mapping[str, str]] -> Query parameters.

        Returns:
            dict[str, object] -> Raw Graph payload.
        """
        response = self.http_client.get(self._build_url(path_or_url), params=params)
        self._raise_for_status(response)
        return cast(dict[str, object], response.json())

    def _stream_graph_file_to_gcs(
        self,
        *,
        drive_id: str,
        item_id: str,
        destination_object_name: str,
        mime_type: str,
        source_item: SharePointDriveItem,
        user_id: str,
    ) -> None:
        """Streams a SharePoint file download into the GCS landing zone.

        Args:
            drive_id: str -> Microsoft Graph drive ID.
            item_id: str -> Microsoft Graph driveItem ID.
            destination_object_name: str -> Landing-zone object path.
            mime_type: str -> Destination object content type.
            source_item: SharePointDriveItem -> Source file metadata.
            user_id: str -> Uploader user identifier stored in metadata.

        Returns:
            None -> Writes the object into GCS.
        """
        drive_segment = _quote_graph_segment(drive_id)
        item_segment = _quote_graph_segment(item_id)
        download_path = f"/drives/{drive_segment}/items/{item_segment}/content"
        storage_client = _build_storage_client()
        bucket = storage_client.bucket(SHAREPOINT_LANDING_ZONE_CONFIG.bucket_name)
        blob = bucket.blob(destination_object_name)

        with self.http_client.stream("GET", self._build_url(download_path)) as response:
            self._raise_for_status(response)
            with blob.open("wb", content_type=mime_type) as writer:
                for chunk in response.iter_bytes(
                    chunk_size=SHAREPOINT_LANDING_ZONE_CONFIG.upload_chunk_size_bytes
                ):
                    if chunk:
                        writer.write(chunk)

        blob.metadata = {
            "source": "sharepoint",
            "source_drive_id": drive_id,
            "source_item_id": item_id,
            "source_web_url": source_item.web_url or "",
            "uploader": user_id,
        }
        blob.patch()

    def _grant_landing_zone_read_access(
        self, folder_prefix: str, user_email: str
    ) -> None:
        """Grants conditional read access to the user's landing-zone namespace.

        Args:
            folder_prefix: str -> Namespace prefix rooted at app/user.
            user_email: str -> User principal to grant object-viewer access.

        Returns:
            None -> Mutates the bucket IAM policy if needed.
        """
        storage_client = _build_storage_client()
        bucket_name = SHAREPOINT_LANDING_ZONE_CONFIG.bucket_name
        bucket = storage_client.bucket(bucket_name)
        resource_prefix = f"projects/_/buckets/{bucket_name}/objects/{folder_prefix}"
        condition_expr = f'resource.name.startsWith("{resource_prefix}")'
        iam_policy = bucket.get_iam_policy(requested_policy_version=3)
        iam_policy.version = 3

        already_granted = any(
            binding.get("role") == "roles/storage.objectViewer"
            and f"user:{user_email}" in binding.get("members", set())
            and (binding.get("condition") or {}).get("expression") == condition_expr
            for binding in iam_policy.bindings
        )
        if already_granted:
            logger.debug("Landing-zone IAM binding already exists for '{}'", user_email)
            return

        iam_policy.bindings.append(
            {
                "role": "roles/storage.objectViewer",
                "members": {f"user:{user_email}"},
                "condition": {
                    "title": "sharepoint-landing-zone-read-access",
                    "expression": condition_expr,
                },
            }
        )
        bucket.set_iam_policy(iam_policy)

    def _build_children_path(
        self,
        drive_id: str,
        item_id: Optional[str],
        folder_path: Optional[str],
    ) -> str:
        """Builds the Graph children endpoint from one folder selector."""
        drive_segment = _quote_graph_segment(drive_id)
        if item_id:
            return f"/drives/{drive_segment}/items/{_quote_graph_segment(item_id)}/children"
        if folder_path:
            return f"/drives/{drive_segment}/root:/{_quote_graph_path(folder_path)}:/children"
        return f"/drives/{drive_segment}/root/children"

    def _build_landing_zone_object_name(
        self, *, folder_prefix: str, session_id: str, filename: str
    ) -> str:
        """Builds a compliant ADK artifact object name for SharePoint files."""
        current_timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        )
        return (
            f"{folder_prefix}{session_id}/"
            f"{SHAREPOINT_LANDING_ZONE_CONFIG.data_source_prefix}-"
            f"{current_timestamp}-{filename}"
        )

    def _build_url(self, path_or_url: str) -> str:
        """Converts a relative Microsoft Graph path into an absolute URL."""
        if path_or_url.startswith("https://"):
            return path_or_url
        base_url = SHAREPOINT_API_CONFIG.graph_base_url.rstrip("/")
        return f"{base_url}/{path_or_url.lstrip('/')}"

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Raises a normalized HTTP error for failed Microsoft Graph responses."""
        if response.is_success:
            return
        message = response.text
        try:
            payload = cast(dict[str, object], response.json())
            error_payload = _as_mapping(payload.get("error"))
            message = _optional_str(error_payload.get("message")) or message
        except Exception:
            pass
        raise RuntimeError(
            f"Microsoft Graph request failed ({response.status_code}): {message}"
        )

    def _build_site(self, payload: Mapping[str, object]) -> SharePointSite:
        """Normalizes a Microsoft Graph site payload into a compact model."""
        return SharePointSite(
            site_id=_required_str(payload.get("id"), "site.id"),
            name=_optional_str(payload.get("name")),
            display_name=_optional_str(payload.get("displayName")),
            web_url=_optional_str(payload.get("webUrl")),
            created_at=_optional_str(payload.get("createdDateTime")),
            last_modified_at=_optional_str(payload.get("lastModifiedDateTime")),
        )

    def _build_site_detail(self, payload: Mapping[str, object]) -> SharePointSiteDetail:
        """Normalizes a Microsoft Graph site payload into an expanded model."""
        site_collection = _as_mapping(payload.get("siteCollection"))
        return SharePointSiteDetail(
            **self._build_site(payload).model_dump(),
            description=_optional_str(payload.get("description")),
            hostname=_optional_str(site_collection.get("hostname")),
            sharepoint_ids=dict(_as_mapping(payload.get("sharepointIds"))),
        )

    def _build_drive(self, payload: Mapping[str, object]) -> SharePointDrive:
        """Normalizes a Microsoft Graph drive payload into a Pydantic model."""
        return SharePointDrive(
            drive_id=_required_str(payload.get("id"), "drive.id"),
            name=_required_str(payload.get("name"), "drive.name"),
            drive_type=_optional_str(payload.get("driveType")),
            web_url=_optional_str(payload.get("webUrl")),
            created_at=_optional_str(payload.get("createdDateTime")),
            last_modified_at=_optional_str(payload.get("lastModifiedDateTime")),
        )

    def _build_list_resource(
        self, payload: Mapping[str, object]
    ) -> SharePointListResource:
        """Normalizes a Microsoft Graph list payload into a Pydantic model."""
        list_payload = _as_mapping(payload.get("list"))
        return SharePointListResource(
            list_id=_required_str(payload.get("id"), "list.id"),
            name=_optional_str(payload.get("name")),
            display_name=_optional_str(payload.get("displayName")),
            web_url=_optional_str(payload.get("webUrl")),
            list_template=_optional_str(list_payload.get("template")),
            created_at=_optional_str(payload.get("createdDateTime")),
            last_modified_at=_optional_str(payload.get("lastModifiedDateTime")),
        )

    def _build_list_item(self, payload: Mapping[str, object]) -> SharePointListItem:
        """Normalizes a Microsoft Graph listItem payload into a Pydantic model."""
        fields = _json_safe_mapping(_as_mapping(payload.get("fields")))
        return SharePointListItem(
            item_id=_required_str(payload.get("id"), "listItem.id"),
            web_url=_optional_str(payload.get("webUrl")),
            created_at=_optional_str(payload.get("createdDateTime")),
            last_modified_at=_optional_str(payload.get("lastModifiedDateTime")),
            fields=fields,
            text_preview=_build_text_preview(fields),
        )

    def _build_page_summary(
        self, payload: Mapping[str, object]
    ) -> SharePointPageSummary:
        """Normalizes a Microsoft Graph sitePage payload into a summary model."""
        return SharePointPageSummary(
            page_id=_required_str(payload.get("id"), "sitePage.id"),
            name=_optional_str(payload.get("name")),
            title=_optional_str(payload.get("title")),
            web_url=_optional_str(payload.get("webUrl")),
            page_layout=_optional_str(payload.get("pageLayout")),
            promotion_kind=_optional_str(payload.get("promotionKind")),
            created_at=_optional_str(payload.get("createdDateTime")),
            last_modified_at=_optional_str(payload.get("lastModifiedDateTime")),
        )

    def _build_page_content(
        self, payload: Mapping[str, object], *, max_text_chars: int
    ) -> SharePointPageContent:
        """Builds a readable page-content model from a Graph sitePage payload."""
        text_fragments = _extract_text_fragments(payload)
        content_text = "\n".join(text_fragments).strip()
        content_truncated = len(content_text) > max_text_chars
        if content_truncated:
            content_text = content_text[:max_text_chars].rstrip()
        return SharePointPageContent(
            **self._build_page_summary(payload).model_dump(),
            content_text=content_text,
            content_truncated=content_truncated,
            component_count=len(text_fragments),
        )

    def _build_drive_item(self, payload: Mapping[str, object]) -> SharePointDriveItem:
        """Normalizes a Microsoft Graph driveItem payload into a Pydantic model."""
        folder_payload = _as_mapping(payload.get("folder"))
        file_payload = _as_mapping(payload.get("file"))
        package_payload = _as_mapping(payload.get("package"))
        parent_reference = _as_mapping(payload.get("parentReference"))
        return SharePointDriveItem(
            item_id=_required_str(payload.get("id"), "driveItem.id"),
            name=_required_str(payload.get("name"), "driveItem.name"),
            kind=_resolve_item_kind(folder_payload, file_payload, package_payload),
            web_url=_optional_str(payload.get("webUrl")),
            mime_type=_optional_str(file_payload.get("mimeType")),
            size_bytes=_int_or_zero(payload.get("size")),
            child_count=_optional_int(folder_payload.get("childCount")),
            created_at=_optional_str(payload.get("createdDateTime")),
            last_modified_at=_optional_str(payload.get("lastModifiedDateTime")),
            parent_drive_id=_optional_str(parent_reference.get("driveId")),
            parent_item_id=_optional_str(parent_reference.get("id")),
            parent_path=_optional_str(parent_reference.get("path")),
        )


def _build_storage_client() -> storage.Client:
    """Builds a GCS client from Application Default Credentials."""
    credentials, project_id = google.auth.default()
    return storage.Client(credentials=credentials, project=project_id)


def _site_select_fields() -> str:
    """Returns Graph field selection for compact site metadata."""
    return "id,name,displayName,webUrl,createdDateTime,lastModifiedDateTime"


def _site_detail_select_fields() -> str:
    """Returns Graph field selection for expanded site metadata."""
    return (
        "id,name,displayName,webUrl,description,siteCollection,sharepointIds,"
        "createdDateTime,lastModifiedDateTime"
    )


def _page_select_fields() -> str:
    """Returns Graph field selection for SharePoint site pages."""
    return (
        "id,name,title,webUrl,pageLayout,promotionKind,"
        "createdDateTime,lastModifiedDateTime"
    )


def _drive_item_select_fields() -> str:
    """Returns the Graph field selection used for drive item metadata."""
    return (
        "id,name,webUrl,size,file,folder,package,parentReference,"
        "createdDateTime,lastModifiedDateTime"
    )


def _quote_graph_segment(value: str) -> str:
    """Safely quotes one Microsoft Graph path segment while preserving Graph IDs."""
    return quote(value, safe=",:")


def _quote_graph_path(value: str) -> str:
    """Safely quotes a root-relative SharePoint path segment by segment."""
    return "/".join(quote(part, safe="") for part in value.strip("/").split("/"))


def _sanitize_filename(filename: str) -> str:
    """Sanitizes a filename for GCS object names while preserving extensions."""
    sanitized = re.sub(r"[^a-zA-Z0-9.\-_]", "_", filename.strip())
    return sanitized or "sharepoint-file"


def _resolve_item_kind(
    folder_payload: Mapping[str, object],
    file_payload: Mapping[str, object],
    package_payload: Mapping[str, object],
) -> SharePointItemKind:
    """Resolves the driveItem kind based on Graph facets."""
    if file_payload:
        return SharePointItemKind.FILE
    if folder_payload:
        return SharePointItemKind.FOLDER
    if package_payload:
        return SharePointItemKind.PACKAGE
    return SharePointItemKind.UNKNOWN


def _extract_text_fragments(payload: Mapping[str, object]) -> list[str]:
    """Extracts readable text fragments from nested Graph page payloads."""
    fragments: list[str] = []
    ignored_keys = {
        "id",
        "eTag",
        "webUrl",
        "createdDateTime",
        "lastModifiedDateTime",
        "@odata.context",
        "@odata.etag",
    }
    preferred_keys = {
        "title",
        "text",
        "innerHtml",
        "serverProcessedContent",
        "description",
        "caption",
        "altText",
    }

    def visit(value: object, key: str = "") -> None:
        if isinstance(value, Mapping):
            for child_key, child_value in value.items():
                if child_key in ignored_keys:
                    continue
                visit(child_value, str(child_key))
            return
        if isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            for child in value:
                visit(child, key)
            return
        if not isinstance(value, str):
            return
        if key not in preferred_keys and len(value.strip()) < 24:
            return
        cleaned = _clean_text(value)
        if cleaned and cleaned not in fragments:
            fragments.append(cleaned)

    visit(payload)
    return fragments


def _clean_text(value: str) -> str:
    """Converts HTML-ish Graph strings into readable plain text."""
    text = html.unescape(value)
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_text_preview(fields: Mapping[str, object]) -> str:
    """Builds a compact preview from SharePoint list item fields."""
    parts: list[str] = []
    for key, value in fields.items():
        if key.startswith("@") or value in (None, ""):
            continue
        if isinstance(value, (str, int, float, bool)):
            parts.append(f"{key}: {value}")
        elif isinstance(value, list):
            scalar_values = [str(item) for item in value if isinstance(item, str)]
            if scalar_values:
                parts.append(f"{key}: {', '.join(scalar_values)}")
        if len("; ".join(parts)) >= 1000:
            break
    return "; ".join(parts)[:1000]


def _json_safe_mapping(value: Mapping[str, object]) -> dict[str, Any]:
    """Returns a shallow JSON-safe mapping for tool responses."""
    return {str(key): _json_safe_value(val) for key, val in value.items()}


def _json_safe_value(value: object) -> Any:
    """Converts Graph values into basic JSON-compatible values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe_value(item) for item in value]
    return str(value)


def _as_mapping(value: object) -> Mapping[str, object]:
    """Returns a mapping only when the provided value is mapping-like."""
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)
    return {}


def _extract_mapping_list(value: object) -> list[dict[str, object]]:
    """Filters a JSON value collection down to dictionaries only."""
    if not isinstance(value, list):
        return []
    return [cast(dict[str, object], item) for item in value if isinstance(item, dict)]


def _optional_str(value: object) -> Optional[str]:
    """Converts a JSON scalar into an optional string."""
    return value if isinstance(value, str) else None


def _required_str(value: object, field_name: str) -> str:
    """Returns a required Graph string field or raises a clear error."""
    if isinstance(value, str) and value:
        return value
    raise ValueError(
        f"Microsoft Graph response is missing required field: {field_name}"
    )


def _int_or_zero(value: object) -> int:
    """Converts JSON numeric values into a non-negative integer."""
    return value if isinstance(value, int) and value >= 0 else 0


def _optional_int(value: object) -> Optional[int]:
    """Converts JSON numeric values into an optional non-negative integer."""
    return value if isinstance(value, int) and value >= 0 else None
