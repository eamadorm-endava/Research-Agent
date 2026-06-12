import asyncio
from mcp.server.fastmcp import FastMCP
from .schemas import (
    SearchEmailsRequest, SearchEmailsResponse,
    GetEmailRequest, GetEmailResponse,
    SendEmailRequest, SendEmailResponse
)
from .client import OutlookGraphClient
from .security import MicrosoftTokenVerifier

# Note: Authentication settings would be injected here leveraging MicrosoftTokenVerifier
mcp = FastMCP("Outlook MCP Server")

@mcp.tool()
async def search_emails(request: SearchEmailsRequest) -> SearchEmailsResponse:
    """Searches the user's Outlook mailbox."""
    try:
        # TODO: Extract OAuth delegated token from context securely
        mock_token = "MOCK_TOKEN" 
        client = OutlookGraphClient(token=mock_token)
        
        # We use asyncio.to_thread if the client were synchronous, however our client is async.
        results = await client.search_emails(query=request.query, top=request.top)
        
        return SearchEmailsResponse(
            execution_status="SUCCESS",
            emails=results
        )
    except Exception as e:
        return SearchEmailsResponse(execution_status=f"FAILED: {str(e)}", emails=[])

@mcp.tool()
async def get_email(request: GetEmailRequest) -> GetEmailResponse:
    """Retrieves a specific email by its ID."""
    try:
        mock_token = "MOCK_TOKEN" 
        client = OutlookGraphClient(token=mock_token)
        email_data = await client.get_email(request.message_id)
        
        return GetEmailResponse(
            execution_status="SUCCESS",
            email_data=email_data
        )
    except Exception as e:
        return GetEmailResponse(execution_status=f"FAILED: {str(e)}", email_data=None)

@mcp.tool()
async def send_email(request: SendEmailRequest) -> SendEmailResponse:
    """Sends a basic email."""
    try:
        mock_token = "MOCK_TOKEN" 
        client = OutlookGraphClient(token=mock_token)
        await client.send_email(
            to_email=request.to_email,
            subject=request.subject,
            body=request.body
        )
        return SendEmailResponse(execution_status="SUCCESS")
    except Exception as e:
        return SendEmailResponse(execution_status=f"FAILED: {str(e)}")
