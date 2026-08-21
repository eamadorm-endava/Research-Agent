import pytest
from unittest.mock import patch
from pydantic import SecretStr

from mcp_servers.outlook.app.outlook_client import OutlookClient
from mcp_servers.outlook.app.schemas import ListEmailsRequest


@pytest.fixture
def outlook_client():
    client = OutlookClient(access_token=SecretStr("mock-token"))
    OutlookClient._list_emails_cache.clear()
    return client


@pytest.mark.asyncio
async def test_list_emails_filtered_pagination_success(outlook_client):
    """
    Validates that listing emails with filters (non-search) correctly returns
    the requested page from MS Graph API without empty slicing on subsequent pages.
    """
    page_1_raw = [
        {
            "id": f"msg-{i}",
            "subject": f"Email {i}",
            "from": {"emailAddress": {"name": "Sender", "address": "sender@test.com"}},
            "toRecipients": [
                {"emailAddress": {"name": "Me", "address": "me@test.com"}}
            ],
            "receivedDateTime": "2026-06-15T10:00:00Z",
            "bodyPreview": f"Preview {i}",
            "hasAttachments": False,
            "isRead": True,
            "parentFolderId": "inbox",
            "webLink": "https://outlook.office.com/mail/inbox",
        }
        for i in range(1, 11)
    ]
    page_2_raw = [
        {
            "id": f"msg-{i}",
            "subject": f"Email {i}",
            "from": {"emailAddress": {"name": "Sender", "address": "sender@test.com"}},
            "toRecipients": [
                {"emailAddress": {"name": "Me", "address": "me@test.com"}}
            ],
            "receivedDateTime": "2026-06-15T09:00:00Z",
            "bodyPreview": f"Preview {i}",
            "hasAttachments": False,
            "isRead": True,
            "parentFolderId": "inbox",
            "webLink": "https://outlook.office.com/mail/inbox",
        }
        for i in range(11, 21)
    ]

    async def mock_get(path, params=None, headers=None):
        if path == "/me":
            return {"mail": "me@test.com"}
        if path == "/me/mailFolders":
            return {"value": []}
        if path == "/me/messages":
            if params.get("$skip") == 0:
                return {"value": page_1_raw, "@odata.count": 65}
            elif params.get("$skip") == 10:
                return {"value": page_2_raw, "@odata.count": 65}
            return {"value": [], "@odata.count": 65}
        return {"value": []}

    with patch.object(outlook_client, "_get", side_effect=mock_get):
        # Fetch Page 1
        req_page_1 = ListEmailsRequest(
            min_date="2026-06-01", page=1, limit=10, use_cache=True
        )
        emails_1, total_1 = await outlook_client.list_emails(req_page_1)
        assert len(emails_1) == 10
        assert total_1 == 65
        assert emails_1[0]["email_id"] == "msg-1"

        # Fetch Page 2 (Must not return empty list)
        req_page_2 = ListEmailsRequest(
            min_date="2026-06-01", page=2, limit=10, use_cache=True
        )
        emails_2, total_2 = await outlook_client.list_emails(req_page_2)
        assert len(emails_2) == 10
        assert total_2 == 65
        assert emails_2[0]["email_id"] == "msg-11"


@pytest.mark.asyncio
async def test_list_emails_search_pagination_and_caching(outlook_client):
    """
    Validates that free-text search ($search) caches all results and slices in-memory
    correctly across page 1 and page 2.
    """
    search_raw = [
        {
            "id": f"search-msg-{i}",
            "subject": f"Project Update {i}",
            "from": {"emailAddress": {"name": "Boss", "address": "boss@test.com"}},
            "toRecipients": [
                {"emailAddress": {"name": "Me", "address": "me@test.com"}}
            ],
            "receivedDateTime": f"2026-06-{26 - i:02d}T10:00:00Z",
            "bodyPreview": f"Search preview {i}",
            "hasAttachments": False,
            "isRead": True,
            "parentFolderId": "inbox",
            "webLink": "https://outlook.office.com/mail/inbox",
        }
        for i in range(1, 26)  # 25 total matched items
    ]

    async def mock_get(path, params=None, headers=None):
        if path == "/me":
            return {"mail": "me@test.com"}
        if path == "/me/mailFolders":
            return {"value": []}
        if path == "/me/messages":
            return {"value": search_raw}
        return {"value": []}

    with patch.object(outlook_client, "_get", side_effect=mock_get):
        req_p1 = ListEmailsRequest(
            sender_receiver="Boss", page=1, limit=10, use_cache=True
        )
        emails_1, total_1 = await outlook_client.list_emails(req_p1)
        assert len(emails_1) == 10
        assert total_1 == 25
        assert emails_1[0]["email_id"] == "search-msg-1"

        # Page 2 from in-memory cache
        req_p2 = ListEmailsRequest(
            sender_receiver="Boss", page=2, limit=10, use_cache=True
        )
        emails_2, total_2 = await outlook_client.list_emails(req_p2)
        assert len(emails_2) == 10
        assert total_2 == 25
        assert emails_2[0]["email_id"] == "search-msg-11"

        # Page 3 from in-memory cache (last 5 items)
        req_p3 = ListEmailsRequest(
            sender_receiver="Boss", page=3, limit=10, use_cache=True
        )
        emails_3, total_3 = await outlook_client.list_emails(req_p3)
        assert len(emails_3) == 5
        assert total_3 == 25
        assert emails_3[0]["email_id"] == "search-msg-21"
