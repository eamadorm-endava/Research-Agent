import httpx
from loguru import logger
from typing import Any, Tuple
import time
import base64

from pydantic import SecretStr
from .config import OUTLOOK_SERVER_CONFIG
from .schemas import (
    OutlookRecipient,
    ListEmailsRequest,
    EmailTypeOption,
    SortByOption,
)

# =====================================================================
# Standalone Payload Sanitization & Extraction Helpers
# =====================================================================


def sanitize_x500_address(
    address: str, fallback_name: str, dynamic_user_email: str
) -> str:
    """
    Intercepts and cleans internal corporate Exchange routing paths (/O=EXCHANGELABS...)
    to prevent ugly, non-routable strings from leaking to the LLM agent.
    """
    if address.strip().startswith(("/O=", "/o=")):
        return (
            dynamic_user_email
            if dynamic_user_email != "Unknown"
            else (fallback_name or "Unknown Sender")
        )
    return address


def parse_personal_data(entity: dict[str, Any] | None) -> dict[str, Any]:
    """Extracts nested from/recipient blocks into standard dictionary formats."""
    if not entity:
        return {"name": None, "email": "unknown@domain.com"}

    email_address = entity.get("emailAddress", {}) or {}
    return {
        "name": email_address.get("name") or None,
        "email": email_address.get("address") or "unknown@domain.com",
    }


# =====================================================================
# Main Core Outlook Abstraction Client
# =====================================================================


class OutlookClient:
    """Delegates actual external interactions with the MS Graph API."""

    # 1. Class-level tracking caches matching the OneDrive architectural blueprint
    _list_emails_cache: dict[tuple, tuple[float, Tuple[list[dict[str, Any]], int]]] = {}

    # Cache time-to-live configuration (e.g., set to 300 seconds / 5 mins)
    _cache_ttl: int = (
        300  # Or pull from your configuration: OUTLOOK_SERVER_CONFIG.cache_ttl_seconds
    )

    @classmethod
    def _sweep_cache(cls) -> None:
        """
        Sweeps the internal Outlook caches to prevent memory leaks.
        Deletes expired keys, and if still above max size, clears out the oldest entries.
        """
        MAX_CACHE_SIZE = 500
        current_time = time.time()

        if len(cls._list_emails_cache) > MAX_CACHE_SIZE:
            # 1. Purge items where TTL has expired
            expired_keys = [
                k
                for k, (timestamp, _) in cls._list_emails_cache.items()
                for k, (timestamp, _) in cls._list_emails_cache.items()
                if current_time - timestamp >= cls._cache_ttl
            ]
            for k in expired_keys:
                cls._list_emails_cache.pop(k, None)

            # 2. If still bloated, purge the oldest 20% using Least Recently Used (LRU) order
            if len(cls._list_emails_cache) > MAX_CACHE_SIZE:
                sorted_items = sorted(
                    cls._list_emails_cache.items(), key=lambda x: x[1][0]
                )
                num_to_delete = int(len(sorted_items) * 0.2)
                for k, _ in sorted_items[:num_to_delete]:
                    cls._list_emails_cache.pop(k, None)

    def __init__(self, access_token: SecretStr):
        if not access_token or not access_token.get_secret_value():
            raise ValueError("No access token provided for OutlookClient.")

        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {self.access_token.get_secret_value()}",
            "Accept": "application/json",
        }

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Baseline resilient GET execution handler utilizing connection pooling and custom timeouts."""
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

    async def _post(
        self, path: str, json: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Baseline resilient POST handler for outgoing transactional workflows."""
        async with httpx.AsyncClient(
            timeout=OUTLOOK_SERVER_CONFIG.timeout_seconds
        ) as client:
            response = await client.post(
                f"{OUTLOOK_SERVER_CONFIG.graph_api_base_url}{path}",
                headers=self.headers,
                json=json,
            )
            response.raise_for_status()
            if response.content:
                return response.json()
            return None

    async def get_my_email(self) -> str:
        """Dynamically identifies the authenticated context user profile information."""
        try:
            profile = await self._get(
                "/me", params={"$select": "mail,userPrincipalName"}
            )
            return profile.get("mail") or profile.get("userPrincipalName") or "Unknown"
        except Exception as e:
            logger.warning(f"Failed to fetch user email context profile: {e}")
            return "Unknown"

    # =====================================================================
    # Tool 1 Implementation Layer: Folder Architecture Mapping
    # =====================================================================

    async def list_folders(self) -> list[dict[str, Any]]:
        """Maps directly to outlook_list_folders by fetching top-level mail spaces."""
        params = {
            "$top": 50,
            "$select": "id,displayName,totalItemCount,unreadItemCount",
        }
        res = await self._get("/me/mailFolders", params=params)
        return res.get("value", [])

    async def build_folder_display_map(self) -> dict[str, str]:
        """Recursively walks down standard and custom subfolder trees to build an ID-to-Name map."""
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

    # =====================================================================
    # Tool 2 Implementation Layer: Consolidated Multi-Context Mail Listings
    # =====================================================================

    async def list_emails(
        self, criteria: ListEmailsRequest
    ) -> Tuple[list[dict[str, Any]], int]:
        """
        Consolidates global search, folder parsing, date filtering,
        sorting constraints, and pagination boundaries into a unified data payload contract.
        """
        # =====================================================================
        # BLUEPRINT CACHE CHECK ENTRY GATE
        # =====================================================================
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
            print(f"🔑 GENERATED CACHE KEY: {cache_key}")
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
                    print(
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

        # =====================================================================
        # SANITIZER: Detect if the agent populated identical terms across fields
        # =====================================================================
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
                    key=lambda x: (x.get("from", {}) or {})
                    .get("emailAddress", {})
                    .get("address", "")
                    .lower(),
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
        if is_search:
            total_matched = len(processed_list)

        # =====================================================================
        # BLUEPRINT CACHE SAVE EXIT GATE
        # =====================================================================

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
        print(
            f"[CACHE MISS] Page {criteria.page} bulk-fetched via Graph API in: {duration_ms:.2f} ms"
        )

        return final_sliced_list, total_matched

    async def read_email(self, email_id: str) -> dict[str, Any]:
        """Queries exhaustive message information variables expanding attachment detail records array maps."""
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

    # async def download_attachment(self, email_id: str, attachment_id: str) -> bytes:
    #     """Streams byte-array values straight from the binary value token endpoint."""
    #     async with httpx.AsyncClient(timeout=OUTLOOK_SERVER_CONFIG.timeout_seconds) as client:
    #         url = f"{OUTLOOK_SERVER_CONFIG.graph_api_base_url}/me/messages/{email_id}/attachments/{attachment_id}/$value"
    #         response = await client.get(url, headers=self.headers)
    #         response.raise_for_status()
    #         return response.content

    async def download_attachment(self, email_id: str, attachment_id: str) -> bytes:
        """
        Downloads attachment data from Microsoft Graph. Handles standard FileAttachments
        by decoding base64 payload properties safely.
        """
        async with httpx.AsyncClient(
            timeout=OUTLOOK_SERVER_CONFIG.timeout_seconds
        ) as client:
            # Fetch the attachment metadata instead of guessing the $value endpoint format
            url = f"{OUTLOOK_SERVER_CONFIG.graph_api_base_url}/me/messages/{email_id}/attachments/{attachment_id}"
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            attachment_data = response.json()

            # If it's a standard file (PDF, XLSX, DOCX, PNG, etc.)
            if (
                "@odata.type" in attachment_data
                and "#microsoft.graph.fileAttachment" in attachment_data["@odata.type"]
            ):
                content_bytes_b64 = attachment_data.get("contentBytes")
                if not content_bytes_b64:
                    raise ValueError(
                        "Attachment payload is empty or missing 'contentBytes'."
                    )

                # Decode the base64 string directly into raw bytes
                return base64.b64decode(content_bytes_b64)

            # Fallback fallback for ItemAttachments/ReferenceAttachments using the raw $value endpoint
            fallback_url = f"{url}/$value"
            fallback_response = await client.get(fallback_url, headers=self.headers)
            fallback_response.raise_for_status()
            return fallback_response.content

    # =====================================================================
    # Outbound Communications Operations (Preserved Production Workflows)
    # =====================================================================

    async def create_draft(
        self,
        to: list[OutlookRecipient],
        cc: list[OutlookRecipient],
        subject: str,
        body: str,
    ) -> dict[str, Any]:
        payload = {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [self._recipient(recipient) for recipient in to],
            "ccRecipients": [self._recipient(recipient) for recipient in cc],
        }
        result = await self._post("/me/messages", json=payload)
        return result or {}

    async def send_mail(
        self,
        to: list[OutlookRecipient],
        cc: list[OutlookRecipient],
        subject: str,
        body: str,
        save_to_sent_items: bool = True,
    ) -> None:
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [self._recipient(recipient) for recipient in to],
                "ccRecipients": [self._recipient(recipient) for recipient in cc],
            },
            "saveToSentItems": save_to_sent_items,
        }
        await self._post("/me/sendMail", json=payload)

    async def send_draft(self, draft_id: str) -> None:
        await self._post(f"/me/messages/{draft_id}/send")

    @staticmethod
    def _recipient(recipient: OutlookRecipient) -> dict[str, Any]:
        email_address: dict[str, str] = {"address": str(recipient.email)}
        if recipient.name:
            email_address["name"] = recipient.name
        return {"emailAddress": email_address}
