import httpx
from loguru import logger
from typing import Any

from pydantic import SecretStr
from .config import OUTLOOK_SERVER_CONFIG
from .schemas import OutlookRecipient


class OutlookClient:
    """Delegates actual external interactions with the MS Graph API."""
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

    async def _get(self, 
                   path: str, 
                   params: dict[str, Any] | None = None, 
                   headers: dict[str, Any] | None = None) -> dict[str, Any]:
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)

        async with httpx.AsyncClient(timeout=OUTLOOK_SERVER_CONFIG.timeout_seconds) as client:
            response = await client.get(
                f"{OUTLOOK_SERVER_CONFIG.graph_api_base_url}{path}",
                headers=request_headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def _post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=OUTLOOK_SERVER_CONFIG.timeout_seconds) as client:
            response = await client.post(
                f"{OUTLOOK_SERVER_CONFIG.graph_api_base_url}{path}",
                headers=self.headers,
                json=json,
            )
            response.raise_for_status()

            if response.content:
                return response.json()

            return None

    async def get_profile(self) -> dict[str, Any]:
        return await self._get("/me")

    async def list_messages(
        self,
        folder: str = "Inbox",
        top: int = 10,
        unread_only: bool = False,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "$top": top,
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,receivedDateTime,bodyPreview,hasAttachments,webLink",
        }

        filters = []
        if unread_only:
            filters.append("isRead eq false")

        if filters:
            params["$filter"] = " and ".join(filters)

        # In first iteration, keep folder hardcoded or map safe display names.
        path = "/me/mailFolders/inbox/messages" if folder.lower() == "inbox" else "/me/messages"

        return (await self._get(path, params=params)).get("value", [])

    async def search_messages(self, query: str, top: int = 10) -> list[dict[str, Any]]:
        params = {
            "$top": top,
            "$search": f'"{query}"',
            "$select": "id,subject,from,receivedDateTime,bodyPreview,hasAttachments,webLink",
        }

        return (await self._get("/me/messages", params=params)).get("value", [])

    async def get_message(self, message_id: str) -> dict[str, Any]:
        params = {
            "$select": (
                "id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
                "body,hasAttachments,attachments"
            ),
            "$expand": "attachments($select=id,name,contentType,size)",
        }

        return await self._get(f"/me/messages/{message_id}", params=params)

    async def create_draft(
        self,
        to: list[OutlookRecipient],
        cc: list[OutlookRecipient],
        subject: str,
        body: str,
    ) -> dict[str, Any]:
        payload = {
            "subject": subject,
            "body": {
                "contentType": "Text",
                "content": body,
            },
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
                "body": {
                    "contentType": "Text",
                    "content": body,
                },
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