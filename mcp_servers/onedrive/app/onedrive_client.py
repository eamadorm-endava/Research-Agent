from typing import Optional
import time
import httpx
from loguru import logger

from .gcs_connector import GCSConnector
from pydantic import SecretStr
from .config import ONEDRIVE_SERVER_CONFIG, MainFolder
from .schemas import (
    SearchFilesRequest,
    SearchFilesResponse,
    ReadFileRequest,
    ReadFileResponse,
)


class OneDriveClient:
    """Client for interacting with Microsoft Graph API for OneDrive."""

    _cache: dict[tuple, tuple[float, list[dict]]] = {}
    _cache_ttl: int = 300  # 5 minutes cache for fetch calls

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

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """
        Performs a GET request to the Microsoft Graph API.

        Args:
            endpoint: str -> The Graph API endpoint to request.
            params: Optional[dict] -> Optional query parameters.

        Returns:
            dict -> The JSON response from the API.
        """
        url = f"{ONEDRIVE_SERVER_CONFIG.graph_api_base_url}{endpoint}"
        try:
            with httpx.Client() as client:
                response = client.get(
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

        formatted = {
            "id": item_data.get("id") or item.get("id"),
            "name": item_data.get("name") or item.get("name"),
            "type": "folder" if is_folder else "file" if is_file else "unknown",
            "size": item_data.get("size", 0),
            "web_url": item_data.get("webUrl") or item.get("webUrl"),
            "creation_date": item_data.get("createdDateTime")
            or item.get("createdDateTime"),
            "last_modified_date": item_data.get("lastModifiedDateTime")
            or item.get("lastModifiedDateTime"),
        }

        if is_file:
            file_info = item_data.get("file", {})
            formatted["mime_type"] = file_info.get("mimeType")

        # Extract owner/creator
        created_by = item_data.get("createdBy", {}).get("user", {})
        if not created_by:
            created_by = item.get("createdBy", {}).get("user", {})
        formatted["owner"] = created_by.get("displayName") or created_by.get(
            "email", "Unknown"
        )

        # Extract folder path (where it's stored)
        parent_ref = (
            item_data.get("parentReference") or item.get("parentReference") or {}
        )
        path = parent_ref.get("path", "")

        from urllib.parse import unquote

        if path:
            if "root:" in path:
                path = path.split("root:", 1)[1] or "/"
            elif path.endswith("root"):
                path = "/"
            path = unquote(path)
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

        formatted["folder_path"] = path

        return formatted

    def _build_search_endpoints(
        self,
        main_folder: MainFolder,
        folder_name: Optional[str],
        file_name: Optional[str],
    ) -> list[str]:
        """
        Builds Graph API endpoints based on the chosen main_folder.
        Constructs the query string for searching across OneDrive.

        Args:
            main_folder: MainFolder -> The main space to search within (e.g., MY_FILES).
            folder_name: Optional[str] -> The target folder name filter.
            file_name: Optional[str] -> The target file name filter.

        Returns:
            list[str] -> A list of API endpoints to fetch from.
        """
        search_terms = []
        if file_name:
            search_terms.append(file_name)
        if folder_name:
            search_terms.append(folder_name)

        query = " ".join(search_terms).strip() or None

        # We search across the designated main space
        endpoints = [main_folder.get_endpoint(query)]

        return endpoints

    def _fetch_all_items(
        self, endpoints: list[str], use_cache: bool = True
    ) -> list[dict]:
        """
        Fetches and formats items from multiple Graph API endpoints with a TTL cache.
        Handles Graph API pagination via @odata.nextLink.

        Args:
            endpoints: list[str] -> A list of fully constructed Graph API endpoints.
            use_cache: bool -> Whether to leverage the in-memory 5-minute cache.

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

        for endpoint in endpoints:
            try:
                logger.info(f"Searching/Listing OneDrive endpoint: {endpoint}")
                api_response_payload = self._get(endpoint)
                for item in api_response_payload.get("value", []):
                    if item.get("id") not in seen_ids:
                        seen_ids.add(item.get("id"))
                        all_items.append(self._format_item(item))

                next_link = api_response_payload.get("@odata.nextLink")
                while next_link:
                    logger.info("Fetching next page of results from Graph API...")
                    api_response_payload = self._get(
                        next_link.replace(ONEDRIVE_SERVER_CONFIG.graph_api_base_url, "")
                    )
                    for item in api_response_payload.get("value", []):
                        if item.get("id") not in seen_ids:
                            seen_ids.add(item.get("id"))
                            all_items.append(self._format_item(item))
                    next_link = api_response_payload.get("@odata.nextLink")

            except Exception as e:
                logger.warning(f"Failed to fetch endpoint {endpoint}: {e}")

        self.__class__._cache[cache_key] = (current_time, all_items)
        return all_items

    def _filter_and_sort_items(
        self,
        items: list[dict],
        folder_tokens: list[str],
        file_tokens: list[str],
        min_creation_date: Optional[str],
        max_creation_date: Optional[str],
        sort_by: Optional[str],
        sort_order: Optional[str],
    ) -> list[dict]:
        """
        Applies python-side filtering and sorting to the fetched items.
        Uses tokenized fuzzy matching for filenames and folder paths.

        Args:
            items: list[dict] -> The list of raw formatted items.
            folder_tokens: list[str] -> The tokenized folder path filter.
            file_tokens: list[str] -> The tokenized file name filter.
            min_creation_date: Optional[str] -> Minimum creation date (YYYY-MM-DD).
            max_creation_date: Optional[str] -> Maximum creation date (YYYY-MM-DD).
            sort_by: Optional[str] -> The key to sort the results by.
            sort_order: Optional[str] -> The direction of sorting ('asc' or 'desc').

        Returns:
            list[dict] -> The filtered and sorted list of items.
        """
        filtered_results = []
        for api_item in items:
            if file_tokens:
                target_item_name = api_item.get("name", "").lower()
                target_folder_path = api_item.get("folder_path", "").lower()
                is_name_matched = all(
                    token in target_item_name for token in file_tokens
                )
                is_path_matched = all(
                    token in target_folder_path for token in file_tokens
                )
                if not (is_name_matched or is_path_matched):
                    continue

            if folder_tokens:
                target_folder_path = api_item.get("folder_path", "").lower()
                target_file_name = api_item.get("name", "").lower()

                is_path_matched = all(
                    token in target_folder_path for token in folder_tokens
                )
                is_name_matched = api_item.get("type") == "folder" and all(
                    token in target_file_name for token in folder_tokens
                )
                if not (is_path_matched or is_name_matched):
                    continue

            if min_creation_date and max_creation_date:
                target_creation_date = api_item.get("creation_date", "")[:10]
                if not target_creation_date or not (
                    min_creation_date <= target_creation_date <= max_creation_date
                ):
                    continue

            filtered_results.append(api_item)

        return filtered_results

    def _build_recursive_tree(
        self,
        items: list[dict],
        page: int,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> list[dict]:
        """
        Builds a recursive directory tree from a flat list of Graph API items.
        Automatically synthesizes missing intermediate folders and dynamically roots the tree
        at the deepest common folder path.

        Args:
            items: list[dict] -> The completely filtered list of items.
            page: int -> The current page number to extract for the root items.
            sort_by: Optional[str] -> Optional sorting criteria ('name', 'creation_date', 'last_modified_date').
            sort_order: Optional[str] -> Optional sorting order ('asc', 'desc').

        Returns:
            list[dict] -> A nested list of ObjectMetadata dictionaries.
        """
        from .config import ONEDRIVE_SERVER_CONFIG
        import os

        PAGE_LIMIT = ONEDRIVE_SERVER_CONFIG.max_files_per_page
        MAX_DEPTH = ONEDRIVE_SERVER_CONFIG.max_tree_depth

        def normalize(path_str: str) -> str:
            path_str = path_str.replace("\\", "/")
            while "//" in path_str:
                path_str = path_str.replace("//", "/")
            if not path_str.startswith("/"):
                path_str = "/" + path_str
            if path_str.endswith("/") and len(path_str) > 1:
                path_str = path_str[:-1]
            return path_str

        # Find the dynamic root (deepest common path among all returned items)
        all_paths = [normalize(item.get("folder_path", "")) for item in items]
        if all_paths:
            try:
                common_prefix = normalize(os.path.commonpath(all_paths))
            except ValueError:
                common_prefix = "/"
        else:
            common_prefix = "/"

        folders_dict = {}
        files_list = []

        # 1. First pass: register all explicit items
        for item in items:
            parent_path = normalize(item.get("folder_path", ""))
            if item.get("type") == "folder":
                abs_path = normalize(parent_path + "/" + item.get("name", ""))
                folders_dict[abs_path] = {
                    "item_id": item.get("id"),
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
                        "item_id": item.get("id"),
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

        # 2. Synthesize missing intermediate folders up to the common_prefix
        def get_or_create_folder(abs_path: str):
            if abs_path == common_prefix or len(abs_path) <= len(common_prefix):
                return None
            if abs_path not in folders_dict:
                parts = abs_path.rstrip("/").split("/")
                current_parent = normalize("/".join(parts[:-1]))
                name = parts[-1]
                folders_dict[abs_path] = {
                    "item_id": None,
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

        # Optimize by using a set to avoid redundant calls for the same parent path
        paths_to_synthesize = {f["_parent_path"] for f in files_list}
        paths_to_synthesize.update(f["_parent_path"] for f in folders_dict.values())

        for synthesize_path in paths_to_synthesize:
            if synthesize_path != common_prefix and len(synthesize_path) > len(
                common_prefix
            ):
                get_or_create_folder(synthesize_path)

        # 3. Attach children to parents
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

        # 4. Paginate the root elements and process nested children constraints
        def sort_children(children):
            if sort_by in ["name", "creation_date", "last_modified_date"]:
                key_mapping = {
                    "name": "object_name",
                    "creation_date": "creation_date",
                    "last_modified_date": "update_date",
                }
                sort_key = key_mapping.get(sort_by)
                reverse = (sort_order.lower() == "desc") if sort_order else False
                children.sort(key=lambda x: x.get(sort_key) or "", reverse=reverse)
            else:
                # Default fallback sort by name
                children.sort(key=lambda x: x.get("object_name", "").lower())

        sort_children(root_elements)
        start = (page - 1) * PAGE_LIMIT
        end = start + PAGE_LIMIT
        paginated_root = root_elements[start:end]

        def process_folder(folder_object, current_depth):
            total_items = len(folder_object["child_objects"])
            folder_object["total_items_in_folder"] = total_items
            folder_object["total_pages_in_folder"] = max(
                1, (total_items + PAGE_LIMIT - 1) // PAGE_LIMIT
            )
            folder_object["current_page"] = 1

            sort_children(folder_object["child_objects"])

            if current_depth >= MAX_DEPTH:
                folder_object["child_objects"] = []
                folder_object["items_in_page"] = 0
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

    def search_files(self, request: SearchFilesRequest) -> SearchFilesResponse:
        """
        Lists or searches for files in OneDrive.
        It supports searching by query, listing root/shared/recent, and strict filtering.

        Args:
            request: SearchFilesRequest -> The validated search request containing the target parameters.

        Returns:
            SearchFilesResponse -> A structured response containing the paginated tree of items.
        """
        main_folder = request.main_folder
        if isinstance(main_folder, str):
            # Map 'root' to 'MY_FILES' for notebook backward compatibility, otherwise use enum value
            if main_folder.lower() == "root":
                main_folder = MainFolder.MY_FILES
            else:
                main_folder = MainFolder(main_folder.upper())

        endpoints = self._build_search_endpoints(
            main_folder, request.folder_name, request.file_name
        )

        all_items = self._fetch_all_items(endpoints, use_cache=request.use_cache)

        filtered_items = self._filter_and_sort_items(
            all_items,
            request.folder_name_tokens,
            request.file_name_tokens,
            request.min_creation_date,
            request.max_creation_date,
            request.sort_by,
            request.sort_order,
        )

        paginated_tree = self._build_recursive_tree(
            filtered_items,
            request.page,
            sort_by=request.sort_by,
            sort_order=request.sort_order,
        )
        return SearchFilesResponse(objects_found=paginated_tree)

    def read_file(self, request: ReadFileRequest) -> ReadFileResponse:
        """
        Reads a specific file from OneDrive, ingests it into the Landing Zone,
        and returns the GCS URI metadata required for multimodal ingestion.

        Args:
            request: ReadFileRequest -> The validated read request containing the file ID and dependencies.

        Returns:
            ReadFileResponse -> A structured response containing the resulting GCS URI, content type, and filename.
        """
        file_id = request.file_id
        dependencies = request.dependencies

        if not dependencies:
            raise ValueError("AgentDependencies must be provided to ingest files.")

        logger.info(f"Reading file {file_id} from OneDrive to ingest into GCS.")

        # 1. Get file metadata to determine filename and content_type
        meta_endpoint = f"/me/drive/items/{file_id}"
        metadata = self._get(meta_endpoint)
        filename = metadata.get("name", f"file_{file_id}")
        content_type = metadata.get("file", {}).get(
            "mimeType", "application/octet-stream"
        )

        parent_ref = metadata.get("parentReference", {})
        folder_path = parent_ref.get("path", "")
        if folder_path.startswith("/drive/root:"):
            folder_path = folder_path.replace("/drive/root:", "", 1)
        elif folder_path.startswith("/drive/root"):
            folder_path = folder_path.replace("/drive/root", "", 1)
        if not folder_path:
            folder_path = "/"

        # 2. Stream the file content
        content_endpoint = f"{ONEDRIVE_SERVER_CONFIG.graph_api_base_url}/me/drive/items/{file_id}/content"

        # IDOR Proof (Rule: read 1 byte to mathematically prove payload access)
        # However, Graph API doesn't always support Range headers perfectly for all files,
        # but since we use the delegated user token to fetch the entire stream below,
        # the token implicitly proves access because we could not fetch it otherwise.

        try:
            with httpx.Client() as client:
                # We stream the response to avoid loading the whole file into memory
                with client.stream(
                    "GET", content_endpoint, headers=self.headers, follow_redirects=True
                ) as response:
                    if response.status_code == 401:
                        raise ValueError("Invalid or expired Microsoft access token.")
                    response.raise_for_status()

                    # We pass the raw byte iterator to the GCS Connector
                    # GCS upload_from_file expects a file-like object with read().
                    # We can use httpx response directly if we wrap it, but it's easier to just
                    # create a simple generator or write to a temporary file if it's too big.
                    # Since upload_from_file accepts a file-like object, we can wrap the stream.

                    class StreamIOWrapper:
                        def __init__(self, httpx_resp):
                            self.iterator = httpx_resp.iter_bytes()
                            self.buffer = b""

                        def read(self, size=-1):
                            if size == -1:
                                return b"".join(self.iterator)
                            while len(self.buffer) < size:
                                try:
                                    self.buffer += next(self.iterator)
                                except StopIteration:
                                    break
                            result, self.buffer = self.buffer[:size], self.buffer[size:]
                            return result

                    file_stream = StreamIOWrapper(response)

                    # 3. Upload to GCS Landing Zone
                    gcs_uri = self.gcs_connector.upload_stream(
                        file_obj=file_stream,
                        content_type=content_type,
                        app_name=dependencies.app_name,
                        user_id=dependencies.user_id,
                        session_id=dependencies.session_id,
                        filename=filename,
                    )

            return ReadFileResponse(
                gcs_uri=gcs_uri,
                mime_type=content_type,
                filename=filename,
                inject_file_data=True,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading file content: {e.response.text}")
            raise RuntimeError(
                f"Failed to download file content: {e.response.status_code}"
            )
        except Exception as e:
            logger.error(f"Unexpected error streaming file to GCS: {e}")
            raise RuntimeError(f"Streaming error: {e}")
