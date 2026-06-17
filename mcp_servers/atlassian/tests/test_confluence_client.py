import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from mcp_servers.atlassian.app.atlassian.confluence_client import (
    ConfluenceClient,
    html_to_markdown,
)
from mcp_servers.atlassian.app.schemas import (
    ListConfluenceSpacesRequest,
    ListConfluencePagesRequest,
    SearchConfluencePagesRequest,
    ReadConfluencePageRequest,
    CreateConfluencePageRequest,
    UpdateConfluencePageRequest,
    ListConfluencePageAttachmentsRequest,
    GetConfluenceAttachmentDetailsRequest,
    ListConfluencePageCommentsRequest,
    CreateConfluencePageCommentRequest,
    ListConfluencePageLabelsRequest,
)


def test_html_to_markdown() -> None:
    """Test standard HTML storage format parsing to Markdown."""
    html = "<h1>Title</h1><p>This is <strong>bold</strong> and <em>italic</em>.</p><ul><li>Item 1</li></ul>"
    expected = "# Title\n\nThis is **bold** and *italic*.\n\n* Item 1"
    assert html_to_markdown(html) == expected


@pytest.mark.asyncio
@patch("google.cloud.storage.Client")
async def test_list_spaces_success(mock_storage_client) -> None:
    """Test successful space listing."""
    client = ConfluenceClient(
        email="test@example.com",
        token="token123",
        instance_url="https://test.atlassian.net",
        cloud_id="cloud-123",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [{"key": "SPACE", "name": "Space Name", "id": "123"}]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        req = ListConfluenceSpacesRequest()
        res = await client.list_spaces(req)

        assert res.execution_status == "success"
        assert len(res.spaces) == 1
        assert res.spaces[0]["key"] == "SPACE"
        mock_get.assert_called_once()


@pytest.mark.asyncio
@patch("google.cloud.storage.Client")
async def test_list_pages_success(mock_storage_client) -> None:
    """Test successful page listing."""
    client = ConfluenceClient(
        email="test@example.com",
        token="token123",
        instance_url="https://test.atlassian.net",
        cloud_id="cloud-123",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [{"id": "999", "title": "Page Title", "spaceId": "123"}]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        req = ListConfluencePagesRequest(space_id="123")
        res = await client.list_pages(req)

        assert res.execution_status == "success"
        assert len(res.pages) == 1
        assert res.pages[0]["title"] == "Page Title"
        # Ensure space filter is passed as space-id
        args, kwargs = mock_get.call_args
        assert kwargs["params"]["space-id"] == "123"


@pytest.mark.asyncio
@patch("google.cloud.storage.Client")
async def test_search_pages_success(mock_storage_client) -> None:
    """Test successful CQL page search."""
    client = ConfluenceClient(
        email="test@example.com",
        token="token123",
        instance_url="https://test.atlassian.net",
        cloud_id="cloud-123",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [{"id": "999", "title": "Page Title"}]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        req = SearchConfluencePagesRequest(cql="title ~ 'Plan'")
        res = await client.search_pages(req)

        assert res.execution_status == "success"
        assert len(res.pages) == 1
        args, kwargs = mock_get.call_args
        assert kwargs["params"]["cql"] == "title ~ 'Plan'"


@pytest.mark.asyncio
@patch("google.cloud.storage.Client")
async def test_read_page_success(mock_storage_client) -> None:
    """Test reading a page and uploading to GCS Landing Zone."""
    # Setup GCS Bucket mocks
    mock_bucket = MagicMock()
    mock_storage_client.return_value.bucket.return_value = mock_bucket
    mock_bucket.name = "test-bucket"

    client = ConfluenceClient(
        email="test@example.com",
        token="token123",
        instance_url="https://test.atlassian.net",
        cloud_id="cloud-123",
    )
    # Configure landing zone bucket on client
    client.gcs.bucket = mock_bucket
    client.gcs.bucket_name = "test-bucket"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "123",
        "title": "My Page",
        "body": {"storage": {"value": "<p>Content of page</p>"}},
    }

    with (
        patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get,
        patch.object(client.gcs, "upload_stream") as mock_upload,
    ):
        mock_get.return_value = mock_response
        mock_upload.return_value = (
            "gs://test-bucket/app/user/session/atlassian-timestamp-My_Page.md"
        )

        req = ReadConfluencePageRequest(page_id="123")
        res = await client.read_page(req)

        assert res.execution_status == "success"
        assert res.gcs_uri.startswith("gs://test-bucket")
        assert res.filename == "My_Page.md"
        assert res.inject_file_data is True
        mock_upload.assert_called_once()


@pytest.mark.asyncio
@patch("google.cloud.storage.Client")
async def test_create_page_success(mock_storage_client) -> None:
    """Test creating a new Confluence page."""
    client = ConfluenceClient(
        email="test@example.com",
        token="token123",
        instance_url="https://test.atlassian.net",
        cloud_id="cloud-123",
    )

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": "1001", "title": "New Page"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        req = CreateConfluencePageRequest(
            space_id="123", title="New Page", body_html="<p>Body</p>"
        )
        res = await client.create_page(req)

        assert res.execution_status == "success"
        assert res.page["id"] == "1001"
        mock_post.assert_called_once()


@pytest.mark.asyncio
@patch("google.cloud.storage.Client")
async def test_update_page_success(mock_storage_client) -> None:
    """Test updating an existing Confluence page."""
    client = ConfluenceClient(
        email="test@example.com",
        token="token123",
        instance_url="https://test.atlassian.net",
        cloud_id="cloud-123",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "1001", "title": "Updated Title"}

    with patch("httpx.AsyncClient.put", new_callable=AsyncMock) as mock_put:
        mock_put.return_value = mock_response

        req = UpdateConfluencePageRequest(
            page_id="1001",
            version_number=2,
            title="Updated Title",
            body_html="<p>Updated</p>",
        )
        res = await client.update_page(req)

        assert res.execution_status == "success"
        assert res.page["title"] == "Updated Title"
        mock_put.assert_called_once()
        args, kwargs = mock_put.call_args
        assert kwargs["json"]["version"]["number"] == 2


@pytest.mark.asyncio
@patch("google.cloud.storage.Client")
async def test_list_page_attachments_success(mock_storage_client) -> None:
    """Test listing page attachments."""
    client = ConfluenceClient(
        email="test@example.com",
        token="token123",
        instance_url="https://test.atlassian.net",
        cloud_id="cloud-123",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [{"id": "att1", "title": "file.pdf", "mediaType": "application/pdf"}]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        req = ListConfluencePageAttachmentsRequest(page_id="123")
        res = await client.list_page_attachments(req)

        assert res.execution_status == "success"
        assert len(res.attachments) == 1
        assert res.attachments[0]["title"] == "file.pdf"
        mock_get.assert_called_once()


@pytest.mark.asyncio
@patch("google.cloud.storage.Client")
async def test_get_attachment_details_success(mock_storage_client) -> None:
    """Test getting details of a specific attachment."""
    client = ConfluenceClient(
        email="test@example.com",
        token="token123",
        instance_url="https://test.atlassian.net",
        cloud_id="cloud-123",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "att1", "title": "file.pdf"}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        req = GetConfluenceAttachmentDetailsRequest(attachment_id="att1")
        res = await client.get_attachment_details(req)

        assert res.execution_status == "success"
        assert res.attachment["id"] == "att1"


@pytest.mark.asyncio
@patch("google.cloud.storage.Client")
async def test_list_page_comments_success(mock_storage_client) -> None:
    """Test listing page comments."""
    client = ConfluenceClient(
        email="test@example.com",
        token="token123",
        instance_url="https://test.atlassian.net",
        cloud_id="cloud-123",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [{"id": "comm1", "body": {"storage": {"value": "comment text"}}}]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        req = ListConfluencePageCommentsRequest(page_id="123")
        res = await client.list_page_comments(req)

        assert res.execution_status == "success"
        assert len(res.comments) == 1
        assert res.comments[0]["id"] == "comm1"


@pytest.mark.asyncio
@patch("google.cloud.storage.Client")
async def test_create_comment_success(mock_storage_client) -> None:
    """Test creating a footer comment on a page."""
    client = ConfluenceClient(
        email="test@example.com",
        token="token123",
        instance_url="https://test.atlassian.net",
        cloud_id="cloud-123",
    )

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "id": "comm1",
        "body": {"storage": {"value": "text"}},
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        req = CreateConfluencePageCommentRequest(page_id="123", body_html="text")
        res = await client.create_comment(req)

        assert res.execution_status == "success"
        assert res.comment["id"] == "comm1"


@pytest.mark.asyncio
@patch("google.cloud.storage.Client")
async def test_list_page_labels_success(mock_storage_client) -> None:
    """Test listing page labels."""
    client = ConfluenceClient(
        email="test@example.com",
        token="token123",
        instance_url="https://test.atlassian.net",
        cloud_id="cloud-123",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": [{"name": "label1", "id": "lab1"}]}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        req = ListConfluencePageLabelsRequest(page_id="123")
        res = await client.list_page_labels(req)

        assert res.execution_status == "success"
        assert len(res.labels) == 1
        assert res.labels[0]["name"] == "label1"
