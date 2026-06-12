import pytest
from app.schemas import SearchEmailsRequest

def test_search_emails_request_schema():
    req = SearchEmailsRequest(query="test", top=5)
    assert req.query == "test"
    assert req.top == 5
