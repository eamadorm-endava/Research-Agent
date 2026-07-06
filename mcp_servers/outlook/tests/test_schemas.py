from mcp_servers.outlook.app.schemas import ListEmailsRequest, EmailTypeOption


def test_list_emails_request_schema():
    # Test that our actual request model initializes properly with default fallbacks
    req = ListEmailsRequest(body="test", limit=5)

    assert req.body == "test"
    assert req.limit == 5
    assert (
        req.email_type == EmailTypeOption.ALL
    )  # Confirms Enum defaults load correctly
