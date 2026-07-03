# Outlook MCP Server

This is the Model Context Protocol (MCP) server for Microsoft Outlook. It connects to the Microsoft Graph API using Entra ID (OAuth) delegated tokens to perform basic email operations.

## Basic Tools Available
1. `search_emails`: Query emails by keyword or sender using Graph API search.
2. `get_email`: Retrieve the full body of a specific email thread.
3. `list_recent_emails`: Retrieve the top latest emails in the Inbox.
4. `send_email`: Send a simple plain text or HTML email.

## Setup
Local testing should be done within a dev-container. Ensure environment variables are loaded if necessary.
