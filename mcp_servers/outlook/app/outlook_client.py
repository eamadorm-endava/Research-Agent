import httpx
from loguru import logger
from typing import Any, Tuple, Optional
import time

from .gcs_connector import GCSConnector
from pydantic import SecretStr
from .config import OUTLOOK_SERVER_CONFIG
from .schemas import (
    ListEmailsRequest,
    EmailTypeOption,
    SortByOption,
    ReadFileResponse,
)


def sanitize_x500_address(
    address: str, fallback_name: str, dynamic_user_email: str
) -> str:
    """
    Intercepts and cleans internal corporate Exchange routing paths (/O=EXCHANGELABS...).
    Prevents non-routable strings from leaking to the LLM agent.

    Args:
        address: str -> The raw email address string.
        fallback_name: str -> The fallback name if the address is internal.
        dynamic_user_email: str -> The authenticated user's email address.

    Returns:
        str -> The sanitized email address.
    """
    if address.strip().startswith(("/O=", "/o=")):
        return (
            dynamic_user_email
            if dynamic_user_email != "Unknown"
            else (fallback_name or "Unknown Sender")
        )
    return address


def parse_personal_data(entity: dict[str, Any] | None) -> dict[str, Any]:
    """
    Extracts nested from/recipient blocks into standard dictionary formats.

    Args:
        entity: dict[str, Any] | None -> The raw recipient entity from the Graph API.

    Returns:
        dict[str, Any] -> The standardized personal data dictionary.
    """
    if not entity:
        return {"name": None, "email": "unknown@domain.com"}

    email_address = entity.get("emailAddress", {}) or {}
    return {
        "name": email_address.get("name") or None,
        "email": email_address.get("address") or "unknown@domain.com",
    }


class OutlookClient:
    """
    Delegates actual external interactions with the MS Graph API.
    Handles authentication, caching, and data retrieval for Outlook emails and calendar events.
    """

    # 1. Class-level tracking caches matching the OneDrive architectural blueprint
    _list_emails_cache: dict[tuple, tuple[float, Tuple[list[dict[str, Any]], int]]] = {}

    # Cache time-to-live configuration (e.g., set to 300 seconds / 5 mins)
    _cache_ttl: int = OUTLOOK_SERVER_CONFIG.cache_ttl_seconds

    _file_cache: dict[tuple, tuple[float, ReadFileResponse]] = {}

    @classmethod
    def _sweep_cache(cls) -> None:
        """
        Sweeps the internal Outlook caches to prevent memory leaks.
        Deletes expired keys, and if still above max size, clears out the oldest entries.

        Args:
            None

        Returns:
            None -> Sweeps the cache inline.
        """
        MAX_CACHE_SIZE = 500
        current_time = time.time()

        for cache_dict in [cls._list_emails_cache, cls._file_cache]:
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
        Initializes the OutlookClient with the provided access token.

        Args:
            access_token: SecretStr -> The Microsoft Graph API access token (secured via pydantic).

        Returns:
            None -> Initializes the client.
        """
        if not access_token or not access_token.get_secret_value():
            raise ValueError("No access token provided for OutlookClient.")

        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {self.access_token.get_secret_value()}",
            "Accept": "application/json",
        }
        self.gcs_connector = GCSConnector()

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Baseline resilient GET execution handler utilizing connection pooling and custom timeouts.

        Args:
            path: str -> The API endpoint path.
            params: dict[str, Any] | None -> Optional query parameters.
            headers: dict[str, Any] | None -> Optional request headers.

        Returns:
            dict[str, Any] -> The JSON response payload.
        """
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)

        async with httpx.AsyncClient(
            timeout=OUTLOOK_SERVER_CONFIG.timeout_seconds
        ) as client:
            response = await client.get(
                f"{OUTLOOK_SERVER_CONFIG.graph_api_base_url}{path}",
                headers=request_headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def get_my_email(self) -> str:
        """
        Dynamically identifies the authenticated context user profile information.

        Args:
            None

        Returns:
            str -> The authenticated user's email address.
        """
        try:
            profile = await self._get(
                "/me", params={"$select": "mail,userPrincipalName"}
            )
            return profile.get("mail") or profile.get("userPrincipalName") or "Unknown"
        except Exception as e:
            logger.warning(f"Failed to fetch user email context profile: {e}")
            return "Unknown"

    async def list_folders(self) -> list[dict[str, Any]]:
        """
        Maps directly to outlook_list_folders by fetching top-level mail spaces.

        Args:
            None

        Returns:
            list[dict[str, Any]] -> The list of root mail folders.
        """
        params = {
            "$top": 50,
            "$select": "id,displayName,totalItemCount,unreadItemCount",
        }
        res = await self._get("/me/mailFolders", params=params)
        return res.get("value", [])

    async def build_folder_display_map(self) -> dict[str, str]:
        """
        Recursively walks down standard and custom subfolder trees to build an ID-to-Name map.

        Args:
            None

        Returns:
            dict[str, str] -> A mapping of folder IDs to their display names.
        """
        folder_map = {}

        async def crawl(path: str = "/me/mailFolders"):
            try:
                data = await self._get(
                    path,
                    params={"$top": 50, "$select": "id,displayName,childFolderCount"},
                )
                for folder in data.get("value", []):
                    folder_map[folder["id"]] = folder["displayName"]
                    if folder.get("childFolderCount", 0) > 0:
                        await crawl(f"/me/mailFolders/{folder['id']}/childFolders")
            except Exception as e:
                logger.debug(f"Folder tree crawl skip path {path}: {e}")

        await crawl()
        return folder_map

    async def list_emails(
        self, criteria: ListEmailsRequest
    ) -> Tuple[list[dict[str, Any]], int]:
        """
        Consolidates global search, folder parsing, date filtering,
        sorting constraints, and pagination boundaries into a unified data payload contract.

        Args:
            criteria: ListEmailsRequest -> The request payload for listing emails.

        Returns:
            Tuple[list[dict[str, Any]], int] -> A tuple containing the list of processed emails and the total matched count.
        """

        start_time = time.perf_counter()

        cache_key = None
        if criteria.use_cache:
            criteria_dict = criteria.model_dump(exclude={"use_cache"})

            criteria_dict.pop("page", None)
            criteria_dict.pop("limit", None)

            current_time = time.time()

            user_id = "unknown_user"
            if criteria.dependencies:
                user_id = criteria.dependencies.user_id
            criteria_dict["mcp_tenant_user_id"] = user_id

            cache_key = tuple(sorted((k, str(v)) for k, v in criteria_dict.items()))
            logger.debug(f"GENERATED CACHE KEY: {cache_key}")
            if cache_key in self._list_emails_cache:
                timestamp, cached_payload = self._list_emails_cache[cache_key]

                if current_time - timestamp < self._cache_ttl:
                    # Cache Hit! Extract the FULL bulk-fetched array from memory
                    all_processed_emails, total_matched = cached_payload

                    # Slice the data exactly for the requested page right now
                    start_offset = (criteria.page - 1) * criteria.limit
                    end_offset = start_offset + criteria.limit
                    sliced_page_data = all_processed_emails[start_offset:end_offset]

                    duration_ms = (time.perf_counter() - start_time) * 1000
                    logger.debug(
                        f"[CACHE HIT] Page {criteria.page} sliced from memory in: {duration_ms:.4f} ms"
                    )

                    return sliced_page_data, total_matched
                else:
                    self._list_emails_cache.pop(cache_key, None)

        my_email = await self.get_my_email()
        folder_map = await self.build_folder_display_map()
        request_headers: dict[str, str] = {}

        # 1. Routing Endpoint Evaluation Strategy & Smart Folder Fallback
        # FIX: If looking for SENT emails and no folder is specified, explicitly default to 'sentitems'
        if criteria.folder_id:
            path = f"/me/mailFolders/{criteria.folder_id}/messages"
        elif criteria.email_type == EmailTypeOption.SENT:
            path = "/me/mailFolders/sentitems/messages"
        else:
            path = "/me/messages"

        query_params: dict[str, Any] = {}

        # 2. Base Query Parameter Foundations
        query_params.update(
            {
                "$top": 50
                if ("$search" in query_params or criteria.sender_receiver)
                else criteria.limit,
                "$skip": 0
                if ("$search" in query_params or criteria.sender_receiver)
                else (criteria.page - 1) * criteria.limit,
                "$select": "id,subject,from,toRecipients,receivedDateTime,bodyPreview,hasAttachments,isRead,parentFolderId,webLink",
                "$count": "true",
            }
        )

        # 3. Handle Advanced Sorting Assignments
        sort_field = "receivedDateTime"
        if criteria.sort_by == SortByOption.SUBJECT:
            sort_field = "subject"
        elif criteria.sort_by == SortByOption.SENDER:
            sort_field = "from/emailAddress/address"

        query_params["$orderby"] = f"{sort_field} {criteria.sort_order.value}"

        # SANITIZER: Detect if the agent populated identical terms across fields
        raw_search_terms = set()
        if criteria.sender_receiver:
            raw_search_terms.add(criteria.sender_receiver.strip('" '))
        if criteria.email_subject:
            raw_search_terms.add(criteria.email_subject.strip('" '))
        if criteria.body:
            raw_search_terms.add(criteria.body.strip('" '))

        # If all populated parameters are identical, collapse them into a single token
        if len(raw_search_terms) == 1:
            unified_term = list(raw_search_terms)[0]
            criteria.sender_receiver = unified_term
            criteria.email_subject = None
            criteria.body = None

        # 4. Construct Dynamic Filter arrays versus KQL global search clauses
        search_tokens: list[str] = []
        filter_tokens: list[str] = []

        if criteria.sender_receiver:
            search_tokens.append(f'"{criteria.sender_receiver}"')
        if criteria.email_subject:
            search_tokens.append(f'subject:"{criteria.email_subject}"')
        if criteria.body:
            search_tokens.append(f'body:"{criteria.body}"')

        if criteria.is_read is not None:
            filter_tokens.append(f"isRead eq {str(criteria.is_read).lower()}")
        if criteria.min_date:
            filter_tokens.append(f"receivedDateTime ge {criteria.min_date}T00:00:00Z")
        if criteria.max_date:
            filter_tokens.append(f"receivedDateTime le {criteria.max_date}T23:59:59Z")

        # Inject structural values based on explicit constraints configurations
        if search_tokens:
            query_params["$search"] = " AND ".join(search_tokens)
            request_headers["ConsistencyLevel"] = "eventual"
            query_params.pop("$orderby", None)

        if filter_tokens:
            query_params["$filter"] = " and ".join(filter_tokens)

        # 5. Fetch Remote API Payload Data
        is_search = "$search" in query_params and query_params["$search"]
        if is_search:
            # Graph $search restrictions handle tops, but skips require client-side offsets if popped
            query_params.pop("$skip", None)
            query_params.pop("$count", None)
            # Fetch a larger batch for local slicing if search-filtering is performed
            query_params["$top"] = 50

        response_data = await self._get(
            path, params=query_params, headers=request_headers
        )
        raw_messages = response_data.get("value", [])

        # Local python fallback sort since Graph API cannot sort $search requests
        if is_search and raw_messages:
            is_descending = criteria.sort_order.value.lower() == "desc"
            if criteria.sort_by == SortByOption.SUBJECT:
                raw_messages.sort(
                    key=lambda x: (x.get("subject") or "").lower(),
                    reverse=is_descending,
                )
            elif criteria.sort_by == SortByOption.SENDER:
                raw_messages.sort(
                    key=lambda x: (
                        (x.get("from", {}) or {})
                        .get("emailAddress", {})
                        .get("address", "")
                        .lower()
                    ),
                    reverse=is_descending,
                )
            else:
                raw_messages.sort(
                    key=lambda x: x.get("receivedDateTime", ""), reverse=is_descending
                )

        # Pull true server metadata count metrics safely
        total_matched = response_data.get("@odata.count", len(raw_messages))

        # 6. Sanitize, filter by item type choice options, and normalize data schemas
        processed_list: list[dict[str, Any]] = []
        standard_fallbacks = {
            "inbox": "Inbox",
            "sentitems": "Sent Items",
            "deleteditems": "Deleted Items",
            "junkemail": "Junk Email",
            "archive": "Archive",
        }

        for msg in raw_messages:
            web_link = msg.get("webLink", "").lower()
            p_id = msg.get("parentFolderId", "")

            resolved_folder = folder_map.get(p_id, "Unknown Folder")
            if resolved_folder == "Unknown Folder":
                for token, fallback_label in standard_fallbacks.items():
                    if token in p_id.lower() or token in web_link:
                        resolved_folder = fallback_label
                        break

            raw_from = msg.get("from", {}) or {}
            from_obj = raw_from.get("emailAddress", {}) or {}
            raw_sender_address = from_obj.get("address", "") or "unknown@domain.com"
            clean_sender_address = sanitize_x500_address(
                raw_sender_address, from_obj.get("name", ""), my_email
            )

            sender_data_payload = {
                "name": from_obj.get("name") or None,
                "email": clean_sender_address,
            }

            # Type filtering verification checks
            if (
                criteria.email_type == EmailTypeOption.SENT
                and clean_sender_address.lower() != my_email.lower()
            ):
                continue
            if (
                criteria.email_type == EmailTypeOption.RECEIVED
                and clean_sender_address.lower() == my_email.lower()
            ):
                continue

            raw_recipients = msg.get("toRecipients", []) or []
            processed_recipients = [parse_personal_data(r) for r in raw_recipients]

            processed_list.append(
                {
                    "email_id": msg.get("id"),
                    "sender_data": sender_data_payload,
                    "sent_to": processed_recipients,
                    "subject": msg.get("subject") or "",
                    "email_body_preview": msg.get("bodyPreview") or "",
                    "received_date": msg.get("receivedDateTime"),
                    "has_attachments": msg.get("hasAttachments") or False,
                    "is_read": msg.get("isRead") or False,
                    "folder_name": resolved_folder,
                }
            )

        # FIX: If local search-filtering modified our array, slice it manually
        # and match the total length to prevent pagination breaks.
        if is_search or total_matched is None or total_matched == 0:
            total_matched = len(processed_list)

        if criteria.use_cache and cache_key is not None:
            self._sweep_cache()
            # Save the complete, unsliced list of emails to memory
            self._list_emails_cache[cache_key] = (
                time.time(),
                (processed_list, total_matched),
            )

        start_offset = (criteria.page - 1) * criteria.limit
        end_offset = start_offset + criteria.limit
        final_sliced_list = processed_list[start_offset:end_offset]

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            f"[CACHE MISS] Page {criteria.page} bulk-fetched via Graph API in: {duration_ms:.2f} ms"
        )

        return final_sliced_list, total_matched

    async def read_email(self, email_id: str) -> dict[str, Any]:
        """
        Queries exhaustive message information variables expanding attachment detail records array maps.

        Args:
            email_id: str -> The unique identifier of the email.

        Returns:
            dict[str, Any] -> The comprehensive email details payload.
        """
        # 1. Gather environmental details and folder structures
        my_email = await self.get_my_email()
        folder_map = await self.build_folder_display_map()

        params = {
            "$select": "id,subject,from,toRecipients,receivedDateTime,body,bodyPreview,hasAttachments,isRead,parentFolderId,webLink",
            "$expand": "attachments($select=id,name,contentType,size)",
        }

        # 2. Fetch the raw email document payload from Microsoft Graph
        msg = await self._get(f"/me/messages/{email_id}", params=params)

        # 3. Resolve the structural folder name using your mapping ecosystem
        p_id = msg.get("parentFolderId", "")
        web_link = msg.get("webLink", "").lower()

        resolved_folder = folder_map.get(p_id, "Unknown Folder")
        if resolved_folder == "Unknown Folder":
            standard_fallbacks = {
                "inbox": "Inbox",
                "sentitems": "Sent Items",
                "deleteditems": "Deleted Items",
                "junkemail": "Junk Email",
                "archive": "Archive",
            }
            for token, fallback_label in standard_fallbacks.items():
                if token in p_id.lower() or token in web_link:
                    resolved_folder = fallback_label
                    break

        # 4. Unpack and sanitize sender payload metrics
        raw_from = msg.get("from", {}) or {}
        from_obj = raw_from.get("emailAddress", {}) or {}
        raw_sender_address = from_obj.get("address", "") or "unknown@domain.com"
        clean_sender_address = sanitize_x500_address(
            raw_sender_address, from_obj.get("name", ""), my_email
        )

        sender_data_payload = {
            "name": from_obj.get("name") or None,
            "email": clean_sender_address,
        }

        # 5. Process recipient arrays and attachment payload records safely
        raw_recipients = msg.get("toRecipients", []) or []
        processed_recipients = [parse_personal_data(r) for r in raw_recipients]

        raw_attachments = msg.get("attachments", []) or []
        processed_attachments = [
            {
                "attachment_id": att.get("id"),
                "name": att.get("name"),
                "content_type": att.get("contentType"),
                "size": att.get("size"),
                "attachment_type": att.get(
                    "@odata.type", "#microsoft.graph.fileAttachment"
                ),
            }
            for att in raw_attachments
        ]

        # 6. CRITICAL SCHEMA ALIGNMENT:
        # Map the clean fields exactly to what EmailInformationFull fields look like at the root.
        # Notice we map 'receivedDateTime' from Graph to 'received_date' for Pydantic.
        return {
            "email_id": msg.get("id"),
            "sender_data": sender_data_payload,
            "sent_to": processed_recipients,
            "subject": msg.get("subject") or "",
            "email_body_preview": msg.get("bodyPreview") or "",
            "received_date": msg.get(
                "receivedDateTime"
            ),  # <-- Crucial line that stopped the crash
            "has_attachments": msg.get("hasAttachments") or False,
            "is_read": msg.get("isRead") or False,
            "folder_name": resolved_folder,
            "email_body": msg.get("body", {}).get("content", ""),
            "attachments": processed_attachments,
        }

    async def _sync_stream_to_landing_zone(
        self,
        content_endpoint: str,
        content_type: str,
        filename: str,
        file_size: int,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> str:
        """
        Synchronously streams a file from Outlook directly into GCS.

        Args:
            content_endpoint: str -> The download endpoint URL.
            content_type: str -> The MIME type of the file.
            filename: str -> The filename of the attachment.
            file_size: int -> The size of the file in bytes.
            app_name: str -> The name of the calling application.
            user_id: str -> The user identifier.
            session_id: str -> The session identifier.

        Returns:
            str -> The resulting GCS URI of the uploaded file.
        """
        with httpx.Client() as client:
            with client.stream(
                "GET", content_endpoint, headers=self.headers, follow_redirects=True
            ) as response:
                if response.status_code == 401:
                    raise ValueError("Invalid or expired Microsoft access token.")
                response.raise_for_status()

                class SyncStreamIOWrapper:
                    def __init__(self, resp):
                        self.iterator = resp.iter_bytes()
                        self.buffer = b""

                    def read(self, size: int = -1) -> bytes:
                        if size == -1:
                            data = b"".join(self.iterator)
                            result = self.buffer + data
                            self.buffer = b""
                            return result
                        while len(self.buffer) < size:
                            try:
                                self.buffer += next(self.iterator)
                            except StopIteration:
                                break
                        result, self.buffer = self.buffer[:size], self.buffer[size:]
                        return result

                    def tell(self) -> int:
                        return 0

                    def seek(self, offset: int, whence: int = 0) -> int:
                        raise IOError("SyncStreamIOWrapper does not support seeking")

                file_stream = SyncStreamIOWrapper(response)

                return self.gcs_connector.upload_stream(
                    file_obj=file_stream,
                    content_type=content_type,
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename,
                    size=file_size,
                )

    async def read_attachment(
        self,
        email_id: str,
        attachment_id: str,
        dependencies: Any,
        is_calendar: bool = False,
    ) -> dict:
        """
        Fetches attachment metadata and streams it to the Landing Zone.
        Returns a dict with gcs_uri, mime_type, filename, and type.

        Args:
            email_id: str -> The email or event ID.
            attachment_id: str -> The unique attachment ID.
            dependencies: Any -> The session dependencies for GCS upload.
            is_calendar: bool -> Whether the parent item is a calendar event.

        Returns:
            dict -> The attachment response payload including GCS URI or reference link.
        """
        async with httpx.AsyncClient(
            timeout=OUTLOOK_SERVER_CONFIG.timeout_seconds
        ) as client:
            base_url = (
                f"{OUTLOOK_SERVER_CONFIG.graph_api_base_url}/me/events/{email_id}"
                if is_calendar
                else f"{OUTLOOK_SERVER_CONFIG.graph_api_base_url}/me/messages/{email_id}"
            )
            url = f"{base_url}/attachments/{attachment_id}"

            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            attachment_data = response.json()

            odata_type = attachment_data.get("@odata.type", "")

            # If it's a reference attachment (stored in OneDrive/SharePoint)
            if "#microsoft.graph.referenceAttachment" in odata_type:
                return {
                    "is_reference": True,
                    "provider_link": attachment_data.get("sourceUrl"),
                    "name": attachment_data.get("name"),
                }

            # Otherwise, stream the raw binary from /$value endpoint
            content_type = attachment_data.get(
                "contentType", "application/octet-stream"
            )

            from .schemas import DownloadableFiles

            allowed_mimes = [e.value for e in DownloadableFiles]
            if content_type not in allowed_mimes:
                raise ValueError(
                    f"The file extension or MIME type '{content_type}' is not allowed or is not supported yet."
                )

            filename = attachment_data.get("name", f"attachment_{attachment_id}")
            file_size = attachment_data.get("size", 0)

            content_endpoint = f"{url}/$value"

            import asyncio

            gcs_uri = await asyncio.to_thread(
                self._sync_stream_to_landing_zone,
                content_endpoint,
                content_type,
                filename,
                file_size,
                dependencies.app_name,
                dependencies.user_id,
                dependencies.session_id,
            )

            return {
                "is_reference": False,
                "gcs_uri": gcs_uri,
                "mime_type": content_type,
                "filename": filename,
            }

    async def list_calendar_events(
        self,
        max_events: int = 30,
        date_min: Optional[str] = None,
        time_min: Optional[str] = None,
        date_max: Optional[str] = None,
        time_max: Optional[str] = None,
        sort_order: str = "asc",
        search_term: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        """
        Lists calendar events from Graph API with optional date/time/text filters.

        Args:
            max_events: int -> Maximum number of events to return
            date_min: Optional[str] -> Minimum date boundary
            time_min: Optional[str] -> Minimum time boundary
            date_max: Optional[str] -> Maximum date boundary
            time_max: Optional[str] -> Maximum time boundary
            sort_order: str -> Sort direction
            search_term: Optional[str] -> Free text search term

        Returns:
            tuple[list[dict], int] -> Tuple containing the list of events and the total count
        """
        endpoint = "/me/events"
        params: dict[str, Any] = {
            "$top": max_events,
            "$select": "id,subject,bodyPreview,start,end,attendees,organizer,isOnlineMeeting,onlineMeeting,hasAttachments",
            "$orderby": f"start/dateTime {sort_order}",
        }

        filters = []
        if date_min and date_max:
            minimum_time = time_min if time_min else "00:00:00Z"
            maximum_time = time_max if time_max else "23:59:59Z"
            if "+" not in minimum_time and "Z" not in minimum_time:
                minimum_time += "Z"
            if "+" not in maximum_time and "Z" not in maximum_time:
                maximum_time += "Z"

            start_datetime = f"{date_min}T{minimum_time}"
            end_datetime = f"{date_max}T{maximum_time}"

            filters.append(f"start/dateTime ge '{start_datetime}'")
            filters.append(f"end/dateTime le '{end_datetime}'")

        if search_term:
            params["$search"] = f'"{search_term}"'

        if filters:
            params["$filter"] = " and ".join(filters)

        headers = self.headers.copy()
        if search_term or filters:
            headers["ConsistencyLevel"] = "eventual"

        url = f"{OUTLOOK_SERVER_CONFIG.graph_api_base_url}{endpoint}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, headers=headers, params=params, timeout=30.0
            )
            if response.status_code == 401:
                raise ValueError("Invalid or expired Microsoft access token.")
            response.raise_for_status()
            graph_api_response = response.json()

        events = []
        for event_payload in graph_api_response.get("value", []):
            events.append(self._parse_calendar_event(event_payload))

        return events, len(events)

    def _parse_calendar_event(self, event_payload: dict) -> dict:
        """
        Parses a Graph API event into our Calendar schema.

        Args:
            event_payload: dict -> Raw Graph API event dictionary.

        Returns:
            dict -> Formatted event matching Calendar schema.
        """
        start = event_payload.get("start", {}).get("dateTime", "")
        end = event_payload.get("end", {}).get("dateTime", "")
        duration = f"{start} to {end}"

        attendees = []
        organizer_email = (
            event_payload.get("organizer", {}).get("emailAddress", {}).get("address")
        )

        if organizer_email:
            attendees.append(
                {
                    "email": organizer_email,
                    "name": event_payload.get("organizer", {})
                    .get("emailAddress", {})
                    .get("name"),
                    "organizer": True,
                }
            )

        for attendee_data in event_payload.get("attendees", []):
            email = attendee_data.get("emailAddress", {}).get("address")
            if email and email != organizer_email:
                attendees.append(
                    {
                        "email": email,
                        "name": attendee_data.get("emailAddress", {}).get("name"),
                        "organizer": False,
                    }
                )

        join_url = None
        if event_payload.get("isOnlineMeeting"):
            join_url = event_payload.get("onlineMeeting", {}).get("joinUrl")

        return {
            "event_id": event_payload.get("id"),
            "event_name": event_payload.get("subject", ""),
            "event_description": event_payload.get("bodyPreview", ""),
            "start_time": start,
            "duration": duration,
            "attendees": attendees,
            "join_url": join_url,
            "has_attachments": event_payload.get("hasAttachments", False),
            "event_body": event_payload.get("body", {}).get("content", ""),
            "attachments": [],
        }

    async def read_calendar_event(self, event_id: str) -> dict:
        """
        Fetches full details of a specific calendar event including attachments.

        Args:
            event_id: str -> The unique identifier of the event

        Returns:
            dict -> Complete event details dictionary
        """
        endpoint = f"/me/events/{event_id}"
        params = {"$expand": "attachments($select=id,name,contentType,size)"}

        url = f"{OUTLOOK_SERVER_CONFIG.graph_api_base_url}{endpoint}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, headers=self.headers, params=params, timeout=30.0
            )
            if response.status_code == 401:
                raise ValueError("Invalid or expired Microsoft access token.")
            response.raise_for_status()
            event_payload = response.json()

        parsed_event = self._parse_calendar_event(event_payload)

        attachments = []
        for attachment_payload in event_payload.get("attachments", []):
            attachments.append(
                {
                    "attachment_id": attachment_payload.get("id"),
                    "file_name": attachment_payload.get("name", "Unnamed Attachment"),
                    "mime_type": attachment_payload.get(
                        "contentType", "application/octet-stream"
                    ),
                    "size": attachment_payload.get("size", 0),
                }
            )
        parsed_event["attachments"] = attachments

        return parsed_event
