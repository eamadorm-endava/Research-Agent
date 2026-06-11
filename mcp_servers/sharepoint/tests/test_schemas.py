import pytest
from pydantic import ValidationError

from mcp_servers.sharepoint.app.schemas import (
    AgentDependencies,
    BaseRequest,
    IngestDriveItemRequest,
    ListDriveItemsRequest,
)


def test_list_drive_items_request_should_accept_root_folder_when_no_selector() -> None:
    request = ListDriveItemsRequest(drive_id="drive-1", max_results=10)

    assert request.drive_id == "drive-1"
    assert request.item_id is None
    assert request.normalized_folder_path is None


def test_list_drive_items_request_should_reject_two_folder_selectors() -> None:
    with pytest.raises(ValidationError):
        ListDriveItemsRequest(
            drive_id="drive-1",
            item_id="item-1",
            folder_path="Shared Documents/Reports",
            max_results=10,
        )


def test_base_request_should_require_injected_dependencies_for_ingestion() -> None:
    request = BaseRequest()

    with pytest.raises(ValueError, match="Missing injected agent dependencies"):
        _ = request.required_dependencies


def test_ingest_request_should_hide_and_return_dependencies_when_injected() -> None:
    dependencies = AgentDependencies(
        app_name="core_agent",
        user_id="user@example.com",
        session_id="session-1",
    )
    request = IngestDriveItemRequest(
        drive_id="drive-1",
        item_id="item-1",
        filename="report.pdf",
        dependencies=dependencies,
    )

    assert request.required_dependencies.user_id == "user@example.com"
    assert "dependencies" not in request.model_dump()
