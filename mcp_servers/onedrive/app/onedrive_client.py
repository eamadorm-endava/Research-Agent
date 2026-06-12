import os
from typing import Optional, Any
from urllib.parse import unquote
import time
import httpx
from loguru import logger

from .gcs_connector import GCSConnector
from pydantic import SecretStr
from .config import ONEDRIVE_SERVER_CONFIG, MainFolder
from .schemas import (
    FindItemsRequest,
    FindItemsResponse,
    ListFolderContentsRequest,
    ListFolderContentsResponse,
    ReadFileRequest,
    ReadFileResponse,
)


class StreamIOWrapper:
    """
    Wraps an httpx streaming response into a file-like object for GCS upload.

    Args:
        httpx_resp: httpx.Response -> The active streaming HTTP response.
    """

    def __init__(self, httpx_resp):
        """
        Initializes the wrapper around an active HTTP stream.

        Args:
            httpx_resp: httpx.Response -> The active streaming response.

        Returns:
            None -> Initializes the wrapper.
        """
        self.iterator = httpx_resp.iter_bytes()
        self.buffer = b""
        self._pos = 0

    def read(self, size: int = -1) -> bytes:
        """
        Reads bytes from the active HTTP stream.

        Args:
            size: int -> The number of bytes to read, or -1 for all bytes.

        Returns:
            bytes -> The chunk of bytes read from the stream.
        """
        if size == -1:
            data = b"".join(self.iterator)
            result = self.buffer + data
            self.buffer = b""
            self._pos += len(result)
            return result
        while len(self.buffer) < size:
            try:
                self.buffer += next(self.iterator)
            except StopIteration:
                break
        result, self.buffer = self.buffer[:size], self.buffer[size:]
        self._pos += len(result)
        return result

    def tell(self) -> int:
        """
        Reports the current byte offset of the stream.

        Args:
            None

        Returns:
            int -> The current position in the byte stream.
        """
        return self._pos

    def seek(self, offset: int, whence: int = 0) -> int:
        """
        Seeks to a specific position in the stream (only supports rewinding to 0 if already at 0).

        Args:
            offset: int -> The target offset.
            whence: int -> The reference point for the offset.

        Returns:
            int -> The new position.
        """
        if offset == 0 and whence == 0 and self._pos == 0:
            return 0
        raise IOError("StreamIOWrapper does not support seeking")


class OneDriveClient:
    """Client for interacting with Microsoft Graph API for OneDrive."""

    _cache: dict[tuple, tuple[float, list[dict]]] = {}
    _file_cache: dict[tuple, tuple[float, ReadFileResponse]] = {}
    _cache_ttl: int = ONEDRIVE_SERVER_CONFIG.cache_ttl_seconds

    @classmethod
    def _sweep_cache(cls) -> None:
        """
        Periodically sweeps the internal caches to prevent memory leaks.
        Deletes expired keys, and if still above max size, deletes the oldest.

        Args:
            None

        Returns:
            None
        """
        MAX_CACHE_SIZE = 500
        current_time = time.time()

        for cache_dict in [cls._cache, cls._file_cache]:
            if len(cache_dict) > MAX_CACHE_SIZE:
                # 1. Purge expired keys
                expired_keys = [
                    k
                    for k, (timestamp, _) in cache_dict.items()
                    if current_time - timestamp >= cls._cache_ttl
                ]
                for k in expired_keys:
                    cache_dict.pop(k, None)

                # 2. If still too large, purge the oldest 20%
                if len(cache_dict) > MAX_CACHE_SIZE:
                    sorted_items = sorted(cache_dict.items(), key=lambda x: x[1][0])
                    num_to_delete = int(len(sorted_items) * 0.2)
                    for k, _ in sorted_items[:num_to_delete]:
                        cache_dict.pop(k, None)

    def __init__(self, access_token: SecretStr):
        """
        Initializes the OneDriveClient with the provided access token.

        Args:
            access_token: SecretStr -> The Microsoft Graph API access token (secured via pydantic).

        Returns:
            None -> Initializes the client.
        """
        if not access_token or not access_token.get_secret_value():
            raise ValueError("No access token provided for OneDriveClient.")

        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {self.access_token.get_secret_value()}",
            "Accept": "application/json",
        }
        self.gcs_connector = GCSConnector()

    def _normalize_insight_item(self, raw_item: dict) -> dict:
        """
        Normalizes a Microsoft Graph SharedInsight wrapper into a standard DriveItem.
        Returns unmodified standard DriveItems for RECENT/MY_FILES endpoints.

        Args:
            raw_item: dict -> The raw JSON item returned from the Graph API.

        Returns:
            dict -> A standard DriveItem structure representing the object.
        """
        if (
            "resourceVisualization" not in raw_item
            and "resourceReference" not in raw_item
        ):
            return raw_item

        if "resource" in raw_item:
            item = raw_item["resource"]
            if not item.get("name") and "resourceVisualization" in raw_item:
                item["name"] = raw_item["resourceVisualization"].get("title")
            return item

        # Reconstruct standard DriveItem if $expand=resource payload was dropped by Microsoft
        ref_id = raw_item.get("resourceReference", {}).get("id", "")
        drive_id = ""
        item_id = ""
        if "drives/" in ref_id and "/items/" in ref_id:
            parts = ref_id.split("/")
            try:
                drive_id = parts[parts.index("drives") + 1]
                item_id = parts[parts.index("items") + 1]
            except ValueError:
                pass

        vis = raw_item.get("resourceVisualization", {})
        is_folder = vis.get("type") == "Folder"

        constructed_item = {
            "name": vis.get("title"),
            "id": item_id,
            "webUrl": raw_item.get("resourceReference", {}).get("webUrl"),
            "parentReference": {"driveId": drive_id},
            "folder": {} if is_folder else None,
            "file": {"mimeType": vis.get("mediaType")} if not is_folder else None,
            "createdBy": {
                "user": {
                    "displayName": raw_item.get("lastShared", {})
                    .get("sharedBy", {})
                    .get("displayName")
                }
            },
            "createdDateTime": raw_item.get("lastShared", {}).get("sharedDateTime"),
            "lastModifiedDateTime": raw_item.get("lastShared", {}).get(
                "sharedDateTime"
            ),
        }
        return {k: v for k, v in constructed_item.items() if v is not None}

    async def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """
        Performs an asynchronous GET request to the Microsoft Graph API.

        Args:
            endpoint: str -> The Graph API endpoint to request.
            params: Optional[dict] -> Optional query parameters.

        Returns:
            dict -> The JSON response from the API.
        """
        url = f"{ONEDRIVE_SERVER_CONFIG.graph_api_base_url}{endpoint}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url, headers=self.headers, params=params, timeout=30.0
                )

            if response.status_code == 401:
                raise ValueError("Invalid or expired Microsoft access token.")

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.text}")
            raise RuntimeError(
                f"API request failed: {e.response.status_code} - {e.response.text}"
            )
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error calling Graph API: {e}")
            raise RuntimeError(f"Unexpected error: {e}")

    def _extract_folder_path(self, item: dict, item_data: dict) -> str:
        """
        Extracts and normalizes the folder path from a Graph API item.

        Args:
            item: dict -> The raw JSON item.
            item_data: dict -> The nested remoteItem or raw item data.

        Returns:
            str -> The normalized absolute folder path.
        """
        parent_ref = (
            item_data.get("parentReference") or item.get("parentReference") or {}
        )
        path = parent_ref.get("path", "")

        if path:
            if "root:" in path:
                path = path.split("root:", 1)[1] or "/"
            elif path.endswith("root"):
                path = "/"
            path = unquote(path)

            # Normalize OneDrive Business paths by stripping the hidden /Documents root
            if path.startswith("/Documents/"):
                path = path.replace("/Documents", "", 1)
            elif path == "/Documents":
                path = "/"
        else:
            # Fallback to webUrl if path is entirely missing
            web_url = item_data.get("webUrl") or item.get("webUrl") or ""
            if "/Documents/" in web_url:
                after_docs = web_url.split("/Documents/", 1)[1]
                if "/" in after_docs:
                    path = "/" + unquote(after_docs.rsplit("/", 1)[0])
                else:
                    path = "/"
            else:
                path = "/"

        if not path.startswith("/"):
            path = "/" + path

        return path

    def _format_item(self, item: dict) -> dict:
        """
        Formats the raw Graph API item into a cleaner dictionary with requested metadata.
        Handles both regular and shared (remoteItem) structures.

        Args:
            item: dict -> The raw JSON item from the Graph API.

        Returns:
            dict -> The formatted item with standardized keys.
        """
        # Handle shared items which encapsulate the actual item in 'remoteItem'
        item_data = item.get("remoteItem", item)

        is_folder = "folder" in item_data
        is_file = "file" in item_data

        item_id = item_data.get("id") or item.get("id")

        # Extract parentReference early for Smart ID and Path
        parent_ref = (
            item_data.get("parentReference") or item.get("parentReference") or {}
        )
        drive_id = parent_ref.get("driveId")
        if drive_id and item_id:
            item_id = f"{drive_id}|{item_id}"

        # Foolproof name extraction
        name = item_data.get("name") or item.get("name") or "Unknown Item"

        formatted = {
            "id": item_id,
            "name": name,
            "type": "folder" if is_folder else "file" if is_file else "unknown",
            "size": item_data.get("size", 0),
            "web_url": item_data.get("webUrl") or item.get("webUrl"),
            "creation_date": item_data.get("createdDateTime")
            or item.get("createdDateTime"),
            "last_modified_date": item_data.get("lastModifiedDateTime")
            or item.get("lastModifiedDateTime"),
            "folder_path": self._extract_folder_path(item, item_data),
        }

        if is_file:
            file_info = item_data.get("file", {})
            formatted["mime_type"] = file_info.get("mimeType")
        elif is_folder:
            folder_info = item_data.get("folder", {})
            formatted["child_count"] = folder_info.get("childCount", 0)

        # Extract owner/creator
        created_by = item_data.get("createdBy", {}).get("user", {})
        if not created_by:
            created_by = item.get("createdBy", {}).get("user", {})
        formatted["owner"] = created_by.get("displayName") or created_by.get(
            "email", "Unknown"
        )

        return formatted

    async def _build_search_endpoints(
        self,
        main_folder: MainFolder,
        item_name: str,
    ) -> list[str]:
        """
        Builds Graph API endpoints based on the chosen main_folder.
        Constructs the query string for searching across OneDrive.

        Args:
            main_folder: MainFolder -> The main space to search within (e.g., MY_FILES).
            item_name: Optional[str] -> The target item name filter.

        Returns:
            list[str] -> A list of API endpoints to fetch from.
        """
        query = item_name.strip()

        # We search across the designated main space
        endpoints = [main_folder.get_endpoint(query)]

        if main_folder == MainFolder.SHARED_WITH_ME:
            try:
                # To support recursive discovery, we fetch the shared items and
                # append a remote search endpoint for every shared folder.
                shared_res = await self._get("/me/insights/shared?$expand=resource")
                for insight_item in shared_res.get("value", []):
                    item = self._normalize_insight_item(insight_item)
                    remote_item = item.get("remoteItem", item)
                    if "folder" in remote_item:
                        drive_id = remote_item.get("parentReference", {}).get("driveId")
                        item_id = remote_item.get("id")
                        if drive_id and item_id:
                            endpoints.append(
                                f"/drives/{drive_id}/items/{item_id}/search(q='{query}')"
                            )
            except Exception as e:
                logger.error(
                    f"Failed to fetch shared items for search construction: {e}"
                )

        return endpoints

    async def _fetch_all_items(
        self, endpoints: list[str], use_cache: bool = True, strict: bool = False
    ) -> list[dict]:
        """
        Fetches and formats items from multiple Graph API endpoints with a TTL cache.
        Handles Graph API pagination via @odata.nextLink.

        Args:
            endpoints: list[str] -> A list of fully constructed Graph API endpoints.
            use_cache: bool -> Whether to leverage the in-memory 5-minute cache.
            strict: bool -> Whether to raise exceptions on HTTP errors instead of catching them.

        Returns:
            list[dict] -> A complete list of fetched and formatted items.
        """
        cache_key = (tuple(endpoints), hash(self.access_token.get_secret_value()))
        current_time = time.time()

        if use_cache and cache_key in self.__class__._cache:
            timestamp, cached_items = self.__class__._cache[cache_key]
            if current_time - timestamp < self.__class__._cache_ttl:
                logger.info("Returning cached results for endpoints.")
                return cached_items

        all_items = []
        seen_ids = set()
        EXCLUDED_PATHS = ("/Forms", "/SiteAssets", "/Lists")

        for endpoint in endpoints:
            try:
                next_link = endpoint
                while next_link:
                    logger.info(f"Fetching OneDrive endpoint: {next_link}")
                    url_to_fetch = next_link.replace(
                        ONEDRIVE_SERVER_CONFIG.graph_api_base_url, ""
                    )
                    api_response_payload = await self._get(url_to_fetch)

                    for raw_item in api_response_payload.get("value", []):
                        item = self._normalize_insight_item(raw_item)
                        item_data = item.get("remoteItem", item)
                        actual_id = item_data.get("id") or item.get("id")
                        if actual_id and actual_id not in seen_ids:
                            seen_ids.add(actual_id)
                            formatted = self._format_item(item)
                            fpath = formatted.get("folder_path", "")
                            if not fpath.startswith(EXCLUDED_PATHS):
                                all_items.append(formatted)

                    next_link = api_response_payload.get("@odata.nextLink")

            except Exception as e:
                logger.warning(f"Failed to fetch endpoint {endpoint}: {e}")
                if strict:
                    raise RuntimeError(str(e))

        self.__class__._sweep_cache()
        self.__class__._cache[cache_key] = (current_time, all_items)
        return all_items

    def _filter_and_sort_items(
        self,
        items: list[dict],
        item_tokens: list[str],
        min_creation_date: Optional[str],
        max_creation_date: Optional[str],
        min_last_modified_date: Optional[str],
        max_last_modified_date: Optional[str],
        sort_by: Optional[str],
        sort_order: Optional[str],
    ) -> list[dict]:
        """
        Applies python-side filtering and sorting to the fetched items.
        Uses tokenized fuzzy matching for item names and folder paths.

        Args:
            items: list[dict] -> The list of raw formatted items.
            item_tokens: list[str] -> The tokenized item name filter.
            min_creation_date: Optional[str] -> Minimum creation date (YYYY-MM-DD).
            max_creation_date: Optional[str] -> Maximum creation date (YYYY-MM-DD).
            min_last_modified_date: Optional[str] -> Minimum last modified date (YYYY-MM-DD).
            max_last_modified_date: Optional[str] -> Maximum last modified date (YYYY-MM-DD).
            sort_by: Optional[str] -> The key to sort the results by.
            sort_order: Optional[str] -> The direction of sorting ('asc' or 'desc').

        Returns:
            list[dict] -> The filtered list of items.
        """
        filtered_results = []
        for api_item in items:
            if item_tokens:
                target_item_name = api_item.get("name", "").lower()
                target_folder_path = api_item.get("folder_path", "").lower()
                is_matched = all(
                    token in target_item_name or token in target_folder_path
                    for token in item_tokens
                )
                if not is_matched:
                    continue

            if min_creation_date and max_creation_date:
                target_creation_date = api_item.get("creation_date", "")[:10]
                if not target_creation_date or not (
                    min_creation_date <= target_creation_date <= max_creation_date
                ):
                    continue

            if min_last_modified_date and max_last_modified_date:
                target_modified_date = api_item.get("last_modified_date", "")[:10]
                if not target_modified_date or not (
                    min_last_modified_date
                    <= target_modified_date
                    <= max_last_modified_date
                ):
                    continue

            filtered_results.append(api_item)

        # Apply global sorting if needed
        if sort_by in ["object_name", "creation_date", "update_date"]:
            key_mapping = {
                "object_name": "name",
                "creation_date": "creation_date",
                "update_date": "last_modified_date",
            }
            sort_key = key_mapping.get(sort_by)
            reverse = (sort_order.lower() == "desc") if sort_order else False
            filtered_results.sort(key=lambda x: x.get(sort_key) or "", reverse=reverse)

        return filtered_results

    def _normalize_path(self, path_str: str) -> str:
        """
        Normalizes a folder path by resolving slashes and trailing characters.

        Args:
            path_str: str -> The raw path string.

        Returns:
            str -> The normalized absolute path.
        """
        path_str = path_str.replace("\\", "/")
        while "//" in path_str:
            path_str = path_str.replace("//", "/")
        if not path_str.startswith("/"):
            path_str = "/" + path_str
        if path_str.endswith("/") and len(path_str) > 1:
            path_str = path_str[:-1]
        return path_str

    def _extract_explicit_items(self, items: list[dict]) -> tuple[dict, list]:
        """
        Extracts and separates folders and files from raw Graph API items.

        Args:
            items: list[dict] -> The list of explicit items to extract.

        Returns:
            tuple[dict, list] -> A tuple containing the folders dictionary and files list.
        """
        folders_dict = {}
        files_list = []
        for item in items:
            parent_path = self._normalize_path(item.get("folder_path", ""))
            if item.get("type") == "folder":
                abs_path = self._normalize_path(
                    parent_path + "/" + item.get("name", "")
                )
                folders_dict[abs_path] = {
                    "folder_id": item.get("id"),
                    "object_name": item.get("name"),
                    "creation_date": item.get("creation_date"),
                    "update_date": item.get("last_modified_date"),
                    "owner": item.get("owner"),
                    "folder_path": parent_path,
                    "url": item.get("web_url"),
                    "object_type": "folder",
                    "child_objects": [],
                    "_abs_path": abs_path,
                    "_parent_path": parent_path,
                }
            else:
                files_list.append(
                    {
                        "file_id": item.get("id"),
                        "object_name": item.get("name"),
                        "creation_date": item.get("creation_date"),
                        "update_date": item.get("last_modified_date"),
                        "owner": item.get("owner"),
                        "folder_path": parent_path,
                        "url": item.get("web_url"),
                        "object_type": "file",
                        "mime_type": item.get("mime_type"),
                        "_parent_path": parent_path,
                    }
                )
        return folders_dict, files_list

    def _synthesize_folders(
        self, folders_dict: dict, files_list: list, common_prefix: str
    ) -> None:
        """
        Synthesizes missing intermediate folders to guarantee tree structure connectivity.

        Args:
            folders_dict: dict -> The dictionary mapping absolute paths to folder objects.
            files_list: list -> The list of explicit files.
            common_prefix: str -> The deepest common parent path for rooting the tree.

        Returns:
            None
        """

        def get_or_create_folder(abs_path: str) -> Optional[dict]:
            """
            Recursively creates missing intermediate folders up to the common root.
            Ensures the tree remains fully connected.

            Args:
                abs_path: str -> The absolute path of the folder to synthesize.

            Returns:
                dict -> The synthesized folder dictionary.
            """
            if abs_path == common_prefix or len(abs_path) <= len(common_prefix):
                return None
            if abs_path not in folders_dict:
                parts = abs_path.rstrip("/").split("/")
                current_parent = self._normalize_path("/".join(parts[:-1]))
                name = parts[-1]
                folders_dict[abs_path] = {
                    "folder_id": None,
                    "object_name": name,
                    "folder_path": current_parent,
                    "object_type": "folder",
                    "child_objects": [],
                    "_abs_path": abs_path,
                    "_parent_path": current_parent,
                }
                if current_parent != common_prefix and len(current_parent) > len(
                    common_prefix
                ):
                    get_or_create_folder(current_parent)
            return folders_dict[abs_path]

        paths_to_synthesize = {f["_parent_path"] for f in files_list}
        paths_to_synthesize.update(f["_parent_path"] for f in folders_dict.values())

        for synthesize_path in paths_to_synthesize:
            if synthesize_path != common_prefix and len(synthesize_path) > len(
                common_prefix
            ):
                get_or_create_folder(synthesize_path)

    def _attach_children_to_parents(
        self, folders_dict: dict, files_list: list, common_prefix: str
    ) -> list[dict]:
        """
        Attaches all fully connected children to their synthesized or explicit parents.

        Args:
            folders_dict: dict -> The fully built dictionary of folder nodes.
            files_list: list -> The list of explicit file nodes.
            common_prefix: str -> The dynamic root path where top-level elements belong.

        Returns:
            list[dict] -> The final list of root-level tree elements.
        """
        root_elements = []
        all_items = files_list + list(folders_dict.values())

        for item in all_items:
            item_parent = item["_parent_path"]
            if item_parent == common_prefix or len(item_parent) <= len(common_prefix):
                root_elements.append(item)
            else:
                if item_parent in folders_dict:
                    folders_dict[item_parent]["child_objects"].append(item)
                else:
                    root_elements.append(item)
        return root_elements

    def _paginate_and_sort_tree(
        self,
        root_elements: list[dict],
        page: int,
        sort_by: Optional[str],
        sort_order: Optional[str],
    ) -> list[dict]:
        """
        Recursively paginates, limits depth, and sorts the synthesized nested folder tree.

        Args:
            root_elements: list[dict] -> The structured root tree elements.
            page: int -> The current page number for the root items.
            sort_by: Optional[str] -> The criteria to sort by (e.g., 'object_name').
            sort_order: Optional[str] -> The direction to sort by ('asc' or 'desc').

        Returns:
            list[dict] -> The finalized, paginated, and sorted tree structure.
        """
        PAGE_LIMIT = ONEDRIVE_SERVER_CONFIG.max_files_per_page
        MAX_DEPTH = ONEDRIVE_SERVER_CONFIG.max_tree_depth

        def sort_children(children: list[dict]) -> None:
            """
            Sorts a list of child objects based on the configured global sort parameters.

            Args:
                children: list[dict] -> The list of child dictionaries to sort in-place.

            Returns:
                None
            """
            if sort_by in ["object_name", "creation_date", "update_date"]:
                sort_key = sort_by
                reverse = (sort_order.lower() == "desc") if sort_order else False
                children.sort(key=lambda x: x.get(sort_key) or "", reverse=reverse)

        sort_children(root_elements)
        start = (page - 1) * PAGE_LIMIT
        end = start + PAGE_LIMIT
        paginated_root = root_elements[start:end]

        def process_folder(folder_object: dict, current_depth: int) -> None:
            """
            Recursively paginates, sorts, and limits the depth of a nested folder tree.

            Args:
                folder_object: dict -> The folder object containing child_objects.
                current_depth: int -> The current traversal depth.

            Returns:
                None
            """
            total_items = len(folder_object["child_objects"])
            folder_object["total_items_in_folder"] = total_items
            folder_object["total_pages_in_folder"] = max(
                1, (total_items + PAGE_LIMIT - 1) // PAGE_LIMIT
            )
            folder_object["current_page"] = 1

            sort_children(folder_object["child_objects"])

            if current_depth >= MAX_DEPTH:
                folder_object["child_objects"] = None
                folder_object["items_in_page"] = None
                folder_object["total_pages_in_folder"] = None
                folder_object["current_page"] = None
            else:
                folder_object["child_objects"] = folder_object["child_objects"][
                    :PAGE_LIMIT
                ]
                folder_object["items_in_page"] = len(folder_object["child_objects"])
                for child in folder_object["child_objects"]:
                    if child["object_type"] == "folder":
                        process_folder(child, current_depth + 1)
                    else:
                        child.pop("_parent_path", None)

            folder_object.pop("_abs_path", None)
            folder_object.pop("_parent_path", None)

        for element in paginated_root:
            if element["object_type"] == "folder":
                process_folder(element, 1)
            element.pop("_abs_path", None)
            element.pop("_parent_path", None)

        return paginated_root

    def _build_recursive_tree(
        self,
        items: list[dict],
        page: int,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        """
        Builds a recursive directory tree from a flat list of Graph API items.
        Automatically synthesizes missing intermediate folders and dynamically roots the tree
        at the deepest common folder path.

        Args:
            items: list[dict] -> The completely filtered list of items.
            page: int -> The current page number to extract for the root items.
            sort_by: Optional[str] -> Optional sorting criteria.
            sort_order: Optional[str] -> Optional sorting order ('asc', 'desc').

        Returns:
            tuple[list[dict], int] -> A tuple containing the paginated nested tree and the total number of root elements.
        """
        all_paths = [
            self._normalize_path(item.get("folder_path", "")) for item in items
        ]
        if all_paths:
            try:
                common_prefix = self._normalize_path(os.path.commonpath(all_paths))
            except ValueError:
                common_prefix = "/"
        else:
            common_prefix = "/"

        folders_dict, files_list = self._extract_explicit_items(items)
        self._synthesize_folders(folders_dict, files_list, common_prefix)
        root_elements = self._attach_children_to_parents(
            folders_dict, files_list, common_prefix
        )
        paginated_root = self._paginate_and_sort_tree(
            root_elements, page, sort_by, sort_order
        )

        return paginated_root, len(root_elements)

    async def find_items(self, request: FindItemsRequest) -> FindItemsResponse:
        """
        Searches globally for files or folders in OneDrive based on item_name.
        This is a 'first discovery' tool that returns a paginated tree of matches.

        Args:
            request: FindItemsRequest -> The validated search request containing the target parameters.

        Returns:
            FindItemsResponse -> A structured response containing the paginated tree of items.
        """
        try:
            main_folder = request.main_folder
            endpoints = await self._build_search_endpoints(
                main_folder, request.item_name
            )

            all_items = await self._fetch_all_items(
                endpoints, use_cache=request.use_cache
            )

            filtered_items = self._filter_and_sort_items(
                all_items,
                request.item_name_tokens,
                request.min_creation_date,
                request.max_creation_date,
                request.min_last_modified_date,
                request.max_last_modified_date,
                request.sort_by,
                request.sort_order,
            )

            # We don't slice the filtered_items here because we want the tree synthesis
            # to construct the full tree of ALL matches so it can accurately calculate
            # nested total_items_in_folder counts. We paginate root elements inside the builder.
            paginated_tree, total_search_matches = self._build_recursive_tree(
                filtered_items,
                page=request.page,
                sort_by=request.sort_by,
                sort_order=request.sort_order,
            )

            PAGE_LIMIT = ONEDRIVE_SERVER_CONFIG.max_files_per_page
            total_pages = max(1, (total_search_matches + PAGE_LIMIT - 1) // PAGE_LIMIT)

            return FindItemsResponse(
                total_search_matches=total_search_matches,
                total_pages=total_pages,
                current_page=request.page,
                items_in_page=len(paginated_tree),
                objects_found=paginated_tree,
            )
        except Exception as e:
            logger.error(f"Error executing find_items: {e}")
            return FindItemsResponse(
                execution_status="error",
                execution_message=f"Failed to find items: {str(e)}",
                total_search_matches=0,
                total_pages=1,
                current_page=1,
                items_in_page=0,
                objects_found=[],
            )

    async def list_folder_contents(
        self, request: ListFolderContentsRequest
    ) -> ListFolderContentsResponse:
        """
        Explicitly lists all files and subfolders strictly inside a specific parent folder.
        Uses deterministic traversal rather than fuzzy search.

        Args:
            request: ListFolderContentsRequest -> The requested folder ID and pagination parameters.

        Returns:
            ListFolderContentsResponse -> A paginated list of immediate child items.
        """
        try:
            folder_id = request.folder_id

            if folder_id in [f.value for f in MainFolder]:
                endpoint = MainFolder(folder_id).list_endpoint
            elif "|" in folder_id:
                drive_id, actual_id = folder_id.split("|", 1)
                endpoint = f"/drives/{drive_id}/items/{actual_id}/children"
            else:
                endpoint = f"/me/drive/items/{folder_id}/children"

            all_items = await self._fetch_all_items(
                [endpoint], use_cache=request.use_cache, strict=True
            )

            # Apply global sorting and date filtering
            all_items = self._filter_and_sort_items(
                all_items,
                None,
                request.min_creation_date,
                request.max_creation_date,
                request.min_last_modified_date,
                request.max_last_modified_date,
                request.sort_by,
                request.sort_order,
            )

            PAGE_LIMIT = ONEDRIVE_SERVER_CONFIG.max_files_per_page

            total_items_in_folder = len(all_items)
            total_pages = max(1, (total_items_in_folder + PAGE_LIMIT - 1) // PAGE_LIMIT)

            start = (request.page - 1) * PAGE_LIMIT
            end = start + PAGE_LIMIT
            paginated_items = all_items[start:end]

            # Convert to ObjectMetadata format (flat list, no tree synthesis required)
            formatted_objects = []
            for item in paginated_items:
                base_metadata = {
                    "object_name": item.get("name"),
                    "creation_date": item.get("creation_date"),
                    "update_date": item.get("last_modified_date"),
                    "owner": item.get("owner"),
                    "folder_path": item.get("folder_path"),
                    "url": item.get("web_url"),
                    "object_type": item.get("type"),
                }
                if item.get("type") == "folder":
                    base_metadata["folder_id"] = item.get("id")
                    base_metadata["total_items_in_folder"] = item.get("child_count", 0)
                    base_metadata["child_objects"] = None
                    base_metadata["items_in_page"] = None
                    base_metadata["total_pages_in_folder"] = None
                    base_metadata["current_page"] = None
                else:
                    base_metadata["file_id"] = item.get("id")
                    base_metadata["mime_type"] = item.get("mime_type")
                formatted_objects.append(base_metadata)

            return ListFolderContentsResponse(
                total_items_in_folder=total_items_in_folder,
                total_pages=total_pages,
                current_page=request.page,
                items_in_page=len(formatted_objects),
                objects_found=formatted_objects,
            )
        except Exception as e:
            logger.error(f"Error executing list_folder_contents: {e}")
            return ListFolderContentsResponse(
                execution_status="error",
                execution_message=f"Failed to list folder contents: {str(e)}",
                total_items_in_folder=0,
                total_pages=1,
                current_page=1,
                items_in_page=0,
                objects_found=[],
            )

    async def _fetch_file_metadata(self, file_id: str) -> dict:
        """
        Fetches the metadata for a specific file from Microsoft Graph API.

        Args:
            file_id: str -> The unique identifier of the file to fetch.

        Returns:
            dict -> The raw JSON metadata of the file.
        """
        if "|" in file_id:
            drive_id, actual_id = file_id.split("|", 1)
            meta_endpoint = f"/drives/{drive_id}/items/{actual_id}"
        else:
            meta_endpoint = f"/me/drive/items/{file_id}"

        try:
            return await self._get(meta_endpoint)
        except Exception as e:
            raise ValueError(f"Failed to fetch file metadata: {str(e)}")

    async def _stream_to_landing_zone(
        self,
        file_id: str,
        content_type: str,
        filename: str,
        file_size: int,
        dependencies: Any,
    ) -> str:
        """
        Streams a file from OneDrive directly into the GCS Landing Zone.

        Args:
            file_id: str -> The unique identifier of the file.
            content_type: str -> The MIME type of the file.
            filename: str -> The name of the file.
            file_size: int -> The size of the file in bytes.
            dependencies: Any -> The session dependencies for the GCS upload.

        Returns:
            str -> The resulting GCS URI of the uploaded file.
        """
        if "|" in file_id:
            drive_id, actual_id = file_id.split("|", 1)
            content_endpoint_suffix = f"/drives/{drive_id}/items/{actual_id}/content"
        else:
            content_endpoint_suffix = f"/me/drive/items/{file_id}/content"

        content_endpoint = (
            f"{ONEDRIVE_SERVER_CONFIG.graph_api_base_url}{content_endpoint_suffix}"
        )

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "GET", content_endpoint, headers=self.headers, follow_redirects=True
            ) as response:
                if response.status_code == 401:
                    raise ValueError("Invalid or expired Microsoft access token.")
                response.raise_for_status()

                file_stream = StreamIOWrapper(response)

                return self.gcs_connector.upload_stream(
                    file_obj=file_stream,
                    content_type=content_type,
                    app_name=dependencies.app_name,
                    user_id=dependencies.user_id,
                    session_id=dependencies.session_id,
                    filename=filename,
                    size=file_size,
                )

    async def read_file(self, request: ReadFileRequest) -> ReadFileResponse:
        """
        Reads a specific file from OneDrive, ingests it into the Landing Zone,
        and returns the GCS URI metadata required for multimodal ingestion.

        Args:
            request: ReadFileRequest -> The validated read request containing the file ID and dependencies.

        Returns:
            ReadFileResponse -> A structured response containing the resulting GCS URI, content type, and filename.
        """
        try:
            file_id = request.file_id
            dependencies = request.dependencies

            if not dependencies:
                raise ValueError("SessionContext must be provided to ingest files.")

            # Check file cache
            cache_key = ("file", file_id, hash(self.access_token.get_secret_value()))
            if request.use_cache and cache_key in self._file_cache:
                cache_time, cached_response = self._file_cache[cache_key]
                if time.time() - cache_time < self._cache_ttl:
                    logger.info(f"Using cached file upload for {file_id}")
                    return cached_response

            logger.info(f"Reading file {file_id} from OneDrive to ingest into GCS.")

            metadata = await self._fetch_file_metadata(file_id)

            if "folder" in metadata:
                raise ValueError(
                    f"The provided ID '{file_id}' corresponds to a folder, but read_file expects a file."
                )

            filename = metadata.get("name", f"file_{file_id}")
            content_type = metadata.get("file", {}).get(
                "mimeType", "application/octet-stream"
            )
            file_size = metadata.get("size")

            gcs_uri = await self._stream_to_landing_zone(
                file_id, content_type, filename, file_size, dependencies
            )

            response = ReadFileResponse(
                gcs_uri=gcs_uri,
                mime_type=content_type,
                filename=filename,
                inject_file_data=True,
            )

            # Store successful read in file cache
            self._sweep_cache()
            self._file_cache[cache_key] = (time.time(), response)
            return response

        except Exception as e:
            logger.error(f"Error fetching and uploading file {request.file_id}: {e}")
            return ReadFileResponse(
                execution_status="error",
                execution_message=f"Failed to read file: {str(e)}",
            )
