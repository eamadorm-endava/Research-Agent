import httpx
import logging

logger = logging.getLogger(__name__)

class OutlookGraphClient:
    """Delegates actual external interactions with the MS Graph API."""
    def __init__(self, token: str):
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.token = token
        
    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    async def search_emails(self, query: str, top: int = 10):
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/me/messages?$search=\"{query}\"&$top={top}&$select=id,subject,from,receivedDateTime"
            resp = await client.get(url, headers=self.headers)
            resp.raise_for_status()
            return resp.json().get("value", [])

    async def get_email(self, message_id: str):
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/me/messages/{message_id}"
            resp = await client.get(url, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    async def send_email(self, to_email: str, subject: str, body: str):
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/me/sendMail"
            payload = {
                "message": {
                    "subject": subject,
                    "body": {"contentType": "Text", "content": body},
                    "toRecipients": [{"emailAddress": {"address": to_email}}]
                },
                "saveToSentItems": "true"
            }
            resp = await client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            return True
