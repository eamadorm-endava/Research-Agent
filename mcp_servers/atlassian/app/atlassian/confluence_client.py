import base64
import io
import re
import httpx
from loguru import logger

from ..gcs_connector import GCSConnector
from ..schemas import (
    ListConfluenceSpacesRequest,
    ListConfluenceSpacesResponse,
    ListConfluencePagesRequest,
    ListConfluencePagesResponse,
    SearchConfluencePagesRequest,
    SearchConfluencePagesResponse,
    GetConfluencePageDetailsRequest,
    GetConfluencePageDetailsResponse,
    ReadConfluencePageRequest,
    ReadConfluencePageResponse,
    CreateConfluencePageRequest,
    CreateConfluencePageResponse,
    UpdateConfluencePageRequest,
    UpdateConfluencePageResponse,
    ListConfluencePageAttachmentsRequest,
    ListConfluencePageAttachmentsResponse,
    GetConfluenceAttachmentDetailsRequest,
    GetConfluenceAttachmentDetailsResponse,
    ListConfluencePageCommentsRequest,
    ListConfluencePageCommentsResponse,
    CreateConfluencePageCommentRequest,
    CreateConfluencePageCommentResponse,
    ListConfluencePageLabelsRequest,
    ListConfluencePageLabelsResponse,
)


def html_to_markdown(html_content: str) -> str:
    """Converts Confluence storage format XHTML to readable Markdown."""
    if not html_content:
        return ""

    # Replace headers
    html = re.sub(r"<h1[^>]*>(.*?)</h1>", r"# \1\n\n", html_content, flags=re.DOTALL)
    html = re.sub(r"<h2[^>]*>(.*?)</h2>", r"## \1\n\n", html, flags=re.DOTALL)
    html = re.sub(r"<h3[^>]*>(.*?)</h3>", r"### \1\n\n", html, flags=re.DOTALL)
    html = re.sub(r"<h4[^>]*>(.*?)</h4>", r"#### \1\n\n", html, flags=re.DOTALL)
    html = re.sub(r"<h5[^>]*>(.*?)</h5>", r"##### \1\n\n", html, flags=re.DOTALL)
    html = re.sub(r"<h6[^>]*>(.*?)</h6>", r"###### \1\n\n", html, flags=re.DOTALL)

    # Replace paragraphs
    html = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", html, flags=re.DOTALL)

    # Replace bold/strong
    html = re.sub(r"<strong[^>]*>(.*?)</strong>", r"**\1**", html, flags=re.DOTALL)
    html = re.sub(r"<b[^>]*>(.*?)</b>", r"**\1**", html, flags=re.DOTALL)

    # Replace italic/em
    html = re.sub(r"<em[^>]*>(.*?)</em>", r"*\1*", html, flags=re.DOTALL)
    html = re.sub(r"<i[^>]*>(.*?)</i>", r"*\1*", html, flags=re.DOTALL)

    # Replace links
    html = re.sub(
        r'<a[^>]*href=["\'](.*?)["\'][^>]*>(.*?)</a>',
        r"[\2](\1)",
        html,
        flags=re.DOTALL,
    )

    # Replace lists
    html = re.sub(r"<li[^>]*>(.*?)</li>", r"* \1\n", html, flags=re.DOTALL)
    html = re.sub(r"<ul[^>]*>(.*?)</ul>", r"\1\n", html, flags=re.DOTALL)
    html = re.sub(r"<ol[^>]*>(.*?)</ol>", r"\1\n", html, flags=re.DOTALL)

    # Replace breaks
    html = re.sub(r"<br\s*/?>", r"\n", html, flags=re.IGNORECASE)

    # Strip remaining HTML tags
    html = re.sub(r"<[^>]+>", "", html)

    # Clean up multiple newlines
    html = re.sub(r"\n{3,}", "\n\n", html)

    return html.strip()


class ConfluenceClient:
    """Wrapper client for the Atlassian Confluence Cloud REST API (v2 and v1 Search)."""

    def __init__(self, email: str, token: str, instance_url: str, cloud_id: str):
        self.email = email
        self.token = token
        self.instance_url = instance_url.rstrip("/")
        self.cloud_id = cloud_id
        self.gcs = GCSConnector()

        # Build basic auth header
        auth_str = f"{self.email}:{self.token}"
        encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        self.headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        logger.info(f"ConfluenceClient initialized for instance {self.instance_url}")

    async def list_spaces(
        self, request: ListConfluenceSpacesRequest
    ) -> ListConfluenceSpacesResponse:
        """Fetch accessible spaces in Confluence."""
        url = f"{self.instance_url}/wiki/api/v2/spaces"
        params = {}
        if request.limit:
            params["limit"] = request.limit
        if request.cursor:
            params["cursor"] = request.cursor

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url, params=params, headers=self.headers, timeout=30
                )
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to list spaces: {resp.status_code} {resp.text}"
                    )
                    return ListConfluenceSpacesResponse(
                        execution_status="error",
                        execution_message=f"Confluence API error: {resp.status_code} {resp.text}",
                        spaces=[],
                    )
                data = resp.json()
                return ListConfluenceSpacesResponse(
                    execution_status="success",
                    spaces=data.get("results", []),
                    next_cursor=data.get("_links", {}).get("next"),
                )
        except Exception as e:
            logger.exception("Exception in list_spaces")
            return ListConfluenceSpacesResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                spaces=[],
            )

    async def list_pages(
        self, request: ListConfluencePagesRequest
    ) -> ListConfluencePagesResponse:
        """Fetch pages in Confluence with optional space filter."""
        url = f"{self.instance_url}/wiki/api/v2/pages"
        params = {}
        if request.space_id:
            params["space-id"] = request.space_id
        if request.limit:
            params["limit"] = request.limit
        if request.cursor:
            params["cursor"] = request.cursor

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url, params=params, headers=self.headers, timeout=30
                )
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to list pages: {resp.status_code} {resp.text}"
                    )
                    return ListConfluencePagesResponse(
                        execution_status="error",
                        execution_message=f"Confluence API error: {resp.status_code} {resp.text}",
                        pages=[],
                    )
                data = resp.json()
                return ListConfluencePagesResponse(
                    execution_status="success",
                    pages=data.get("results", []),
                    next_cursor=data.get("_links", {}).get("next"),
                )
        except Exception as e:
            logger.exception("Exception in list_pages")
            return ListConfluencePagesResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                pages=[],
            )

    async def search_pages(
        self, request: SearchConfluencePagesRequest
    ) -> SearchConfluencePagesResponse:
        """CQL-based page discovery (v1 search)."""
        url = f"{self.instance_url}/wiki/rest/api/content/search"
        params = {"cql": request.cql}
        if request.limit:
            params["limit"] = request.limit
        if request.next_page_token:
            params["nextPageToken"] = request.next_page_token

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url, params=params, headers=self.headers, timeout=30
                )
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to search pages: {resp.status_code} {resp.text}"
                    )
                    return SearchConfluencePagesResponse(
                        execution_status="error",
                        execution_message=f"Confluence API error: {resp.status_code} {resp.text}",
                        pages=[],
                    )
                data = resp.json()
                return SearchConfluencePagesResponse(
                    execution_status="success",
                    pages=data.get("results", []),
                    next_page_token=data.get("nextPageToken"),
                )
        except Exception as e:
            logger.exception("Exception in search_pages")
            return SearchConfluencePagesResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                pages=[],
            )

    async def get_page_details(
        self, request: GetConfluencePageDetailsRequest
    ) -> GetConfluencePageDetailsResponse:
        """Fetch metadata of a single Confluence page."""
        url = f"{self.instance_url}/wiki/api/v2/pages/{request.page_id}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self.headers, timeout=30)
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to get page details: {resp.status_code} {resp.text}"
                    )
                    return GetConfluencePageDetailsResponse(
                        execution_status="error",
                        execution_message=f"Confluence API error: {resp.status_code} {resp.text}",
                        page=None,
                    )
                page = resp.json()
                return GetConfluencePageDetailsResponse(
                    execution_status="success",
                    page=page,
                )
        except Exception as e:
            logger.exception("Exception in get_page_details")
            return GetConfluencePageDetailsResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                page=None,
            )

    async def read_page(
        self, request: ReadConfluencePageRequest
    ) -> ReadConfluencePageResponse:
        """Fetch page content, translate to Markdown, and stream to GCS Landing Zone."""
        url = f"{self.instance_url}/wiki/api/v2/pages/{request.page_id}"
        params = {"body-format": "storage"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url, params=params, headers=self.headers, timeout=30
                )
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to fetch page body: {resp.status_code} {resp.text}"
                    )
                    return ReadConfluencePageResponse(
                        execution_status="error",
                        execution_message=f"Confluence API error: {resp.status_code} {resp.text}",
                        gcs_uri=None,
                        mime_type=None,
                        filename=None,
                        inject_file_data=False,
                    )

                page_data = resp.json()
                title = page_data.get("title", "Untitled Page")
                # Clean title for filename mapping
                safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")
                filename = f"{safe_title}.md"

                # Extract HTML storage body
                body_html = (
                    page_data.get("body", {}).get("storage", {}).get("value", "")
                )

                # Convert HTML to Markdown
                markdown_text = f"# {title}\n\n" + html_to_markdown(body_html)

                # Convert markdown string to binary stream
                markdown_bytes = markdown_text.encode("utf-8")
                stream = io.BytesIO(markdown_bytes)

                # Fetch DI credentials
                app_name = "core_agent"
                user_id = "user-email@domain.com"
                session_id = "default-session"

                if request.dependencies:
                    app_name = request.dependencies.app_name
                    user_id = request.dependencies.user_id
                    session_id = request.dependencies.session_id

                # Stream upload to GCS Landing Zone
                gcs_uri = self.gcs.upload_stream(
                    file_obj=stream,
                    content_type="text/markdown",
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename,
                    size=len(markdown_bytes),
                )

                return ReadConfluencePageResponse(
                    execution_status="success",
                    gcs_uri=gcs_uri,
                    mime_type="text/markdown",
                    filename=filename,
                    inject_file_data=True,
                )

        except Exception as e:
            logger.exception("Exception in read_page")
            return ReadConfluencePageResponse(
                execution_status="error",
                execution_message=f"Ingestion failure: {str(e)}",
                gcs_uri=None,
                mime_type=None,
                filename=None,
                inject_file_data=False,
            )

    async def create_page(
        self, request: CreateConfluencePageRequest
    ) -> CreateConfluencePageResponse:
        """Create a new page in Confluence."""
        url = f"{self.instance_url}/wiki/api/v2/pages"
        payload = {
            "spaceId": request.space_id,
            "status": "current",
            "title": request.title,
            "body": {"representation": "storage", "value": request.body_html},
        }
        if request.parent_id:
            payload["parentId"] = request.parent_id

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url, json=payload, headers=self.headers, timeout=30
                )
                if resp.status_code not in (200, 201):
                    logger.error(
                        f"Failed to create page: {resp.status_code} {resp.text}"
                    )
                    return CreateConfluencePageResponse(
                        execution_status="error",
                        execution_message=f"Confluence API error: {resp.status_code} {resp.text}",
                        page=None,
                    )
                page = resp.json()
                return CreateConfluencePageResponse(
                    execution_status="success",
                    page=page,
                )
        except Exception as e:
            logger.exception("Exception in create_page")
            return CreateConfluencePageResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                page=None,
            )

    async def update_page(
        self, request: UpdateConfluencePageRequest
    ) -> UpdateConfluencePageResponse:
        """Update an existing page in Confluence."""
        url = f"{self.instance_url}/wiki/api/v2/pages/{request.page_id}"
        payload = {
            "id": request.page_id,
            "status": "current",
            "title": request.title,
            "body": {"representation": "storage", "value": request.body_html},
            "version": {"number": request.version_number},
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.put(
                    url, json=payload, headers=self.headers, timeout=30
                )
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to update page: {resp.status_code} {resp.text}"
                    )
                    return UpdateConfluencePageResponse(
                        execution_status="error",
                        execution_message=f"Confluence API error: {resp.status_code} {resp.text}",
                        page=None,
                    )
                page = resp.json()
                return UpdateConfluencePageResponse(
                    execution_status="success",
                    page=page,
                )
        except Exception as e:
            logger.exception("Exception in update_page")
            return UpdateConfluencePageResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                page=None,
            )

    async def list_page_attachments(
        self, request: ListConfluencePageAttachmentsRequest
    ) -> ListConfluencePageAttachmentsResponse:
        """List attachments on a specific page."""
        url = f"{self.instance_url}/wiki/api/v2/pages/{request.page_id}/attachments"
        params = {}
        if request.limit:
            params["limit"] = request.limit
        if request.cursor:
            params["cursor"] = request.cursor

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url, params=params, headers=self.headers, timeout=30
                )
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to list page attachments: {resp.status_code} {resp.text}"
                    )
                    return ListConfluencePageAttachmentsResponse(
                        execution_status="error",
                        execution_message=f"Confluence API error: {resp.status_code} {resp.text}",
                        attachments=[],
                    )
                data = resp.json()
                return ListConfluencePageAttachmentsResponse(
                    execution_status="success",
                    attachments=data.get("results", []),
                    next_cursor=data.get("_links", {}).get("next"),
                )
        except Exception as e:
            logger.exception("Exception in list_page_attachments")
            return ListConfluencePageAttachmentsResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                attachments=[],
            )

    async def get_attachment_details(
        self, request: GetConfluenceAttachmentDetailsRequest
    ) -> GetConfluenceAttachmentDetailsResponse:
        """Fetch metadata for a specific attachment."""
        url = f"{self.instance_url}/wiki/api/v2/attachments/{request.attachment_id}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self.headers, timeout=30)
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to get attachment details: {resp.status_code} {resp.text}"
                    )
                    return GetConfluenceAttachmentDetailsResponse(
                        execution_status="error",
                        execution_message=f"Confluence API error: {resp.status_code} {resp.text}",
                        attachment=None,
                    )
                attachment = resp.json()
                return GetConfluenceAttachmentDetailsResponse(
                    execution_status="success",
                    attachment=attachment,
                )
        except Exception as e:
            logger.exception("Exception in get_attachment_details")
            return GetConfluenceAttachmentDetailsResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                attachment=None,
            )

    async def list_page_comments(
        self, request: ListConfluencePageCommentsRequest
    ) -> ListConfluencePageCommentsResponse:
        """List footer comments for a specific page."""
        url = f"{self.instance_url}/wiki/api/v2/pages/{request.page_id}/footer-comments"
        params = {}
        if request.limit:
            params["limit"] = request.limit
        if request.cursor:
            params["cursor"] = request.cursor

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url, params=params, headers=self.headers, timeout=30
                )
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to list page comments: {resp.status_code} {resp.text}"
                    )
                    return ListConfluencePageCommentsResponse(
                        execution_status="error",
                        execution_message=f"Confluence API error: {resp.status_code} {resp.text}",
                        comments=[],
                    )
                data = resp.json()
                return ListConfluencePageCommentsResponse(
                    execution_status="success",
                    comments=data.get("results", []),
                    next_cursor=data.get("_links", {}).get("next"),
                )
        except Exception as e:
            logger.exception("Exception in list_page_comments")
            return ListConfluencePageCommentsResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                comments=[],
            )

    async def create_comment(
        self, request: CreateConfluencePageCommentRequest
    ) -> CreateConfluencePageCommentResponse:
        """Create a comment on a Confluence page."""
        url = f"{self.instance_url}/wiki/api/v2/pages/{request.page_id}/footer-comments"
        payload = {
            "status": "current",
            "body": {"representation": "storage", "value": request.body_html},
        }
        if request.parent_comment_id:
            payload["parentCommentId"] = request.parent_comment_id

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url, json=payload, headers=self.headers, timeout=30
                )
                if resp.status_code not in (200, 201):
                    logger.error(
                        f"Failed to create comment: {resp.status_code} {resp.text}"
                    )
                    return CreateConfluencePageCommentResponse(
                        execution_status="error",
                        execution_message=f"Confluence API error: {resp.status_code} {resp.text}",
                        comment=None,
                    )
                comment = resp.json()
                return CreateConfluencePageCommentResponse(
                    execution_status="success",
                    comment=comment,
                )
        except Exception as e:
            logger.exception("Exception in create_comment")
            return CreateConfluencePageCommentResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                comment=None,
            )

    async def list_page_labels(
        self, request: ListConfluencePageLabelsRequest
    ) -> ListConfluencePageLabelsResponse:
        """List labels associated with a specific page."""
        url = f"{self.instance_url}/wiki/api/v2/pages/{request.page_id}/labels"
        params = {}
        if request.limit:
            params["limit"] = request.limit
        if request.cursor:
            params["cursor"] = request.cursor

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url, params=params, headers=self.headers, timeout=30
                )
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to list page labels: {resp.status_code} {resp.text}"
                    )
                    return ListConfluencePageLabelsResponse(
                        execution_status="error",
                        execution_message=f"Confluence API error: {resp.status_code} {resp.text}",
                        labels=[],
                    )
                data = resp.json()
                return ListConfluencePageLabelsResponse(
                    execution_status="success",
                    labels=data.get("results", []),
                    next_cursor=data.get("_links", {}).get("next"),
                )
        except Exception as e:
            logger.exception("Exception in list_page_labels")
            return ListConfluencePageLabelsResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                labels=[],
            )
