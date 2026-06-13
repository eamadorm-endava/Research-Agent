import pytest
from pydantic import ValidationError

from app.schemas import BaseDateFilterRequest, FindItemsRequest


def test_base_date_filter_request_created_date_window():
    """Test the @model_validator check_created_date_window."""
    # Happy Path
    req = BaseDateFilterRequest(
        min_creation_date="2023-01-01", max_creation_date="2023-01-31"
    )
    assert req.min_creation_date == "2023-01-01"
    assert req.max_creation_date == "2023-01-31"

    # Pair Missing Failure
    with pytest.raises(ValidationError) as exc_info:
        BaseDateFilterRequest(min_creation_date="2023-01-01")
    assert (
        "Both min_creation_date and max_creation_date must be provided together"
        in str(exc_info.value)
    )

    # Inversed Date Failure
    with pytest.raises(ValidationError) as exc_info:
        BaseDateFilterRequest(
            min_creation_date="2023-01-31", max_creation_date="2023-01-01"
        )
    assert "min_creation_date cannot be later than max_creation_date" in str(
        exc_info.value
    )


def test_base_date_filter_request_modified_date_window():
    """Test the @model_validator check_modified_date_window."""
    # Happy Path
    req = BaseDateFilterRequest(
        min_last_modified_date="2023-01-01", max_last_modified_date="2023-01-31"
    )
    assert req.min_last_modified_date == "2023-01-01"
    assert req.max_last_modified_date == "2023-01-31"

    # Pair Missing Failure
    with pytest.raises(ValidationError) as exc_info:
        BaseDateFilterRequest(max_last_modified_date="2023-01-31")
    assert (
        "Both min_last_modified_date and max_last_modified_date must be provided together"
        in str(exc_info.value)
    )

    # Inversed Date Failure
    with pytest.raises(ValidationError) as exc_info:
        BaseDateFilterRequest(
            min_last_modified_date="2023-01-31", max_last_modified_date="2023-01-01"
        )
    assert "min_last_modified_date cannot be later than max_last_modified_date" in str(
        exc_info.value
    )


def test_cleanse_search_terms():
    """Test that slashes and quotes are properly cleansed to avoid Graph API 400s."""
    req = FindItemsRequest(
        item_name="test/file\\name'with\"quotes", main_folder="MY_FILES", page=1
    )
    assert req.item_name == "test file name with quotes"


def test_empty_string_after_cleansing():
    """Test that an empty string or spaces fails validation after cleansing."""
    with pytest.raises(ValidationError) as exc_info:
        FindItemsRequest(item_name="   ", main_folder="MY_FILES", page=1)
    assert "String should have at least 1 character" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        FindItemsRequest(item_name=" / ' \" \\ ", main_folder="MY_FILES", page=1)
    assert "String should have at least 1 character" in str(exc_info.value)


def test_item_name_tokens():
    """Test the computed property item_name_tokens for fuzzy matching."""
    req = FindItemsRequest(
        item_name="Testing_Larger-Folder", main_folder="MY_FILES", page=1
    )
    assert req.item_name_tokens == ["testing", "larger", "folder"]


def test_remove_leaf_nulls_serialization():
    """Test that setting attributes to None effectively removes them during serialization."""
    from app.schemas import FolderMetadata

    folder = FolderMetadata(
        folder_id="123",
        object_name="Deep Leaf",
        object_type="folder",
        folder_path="/root/a/b",
        url="https://test",
        creation_date="2023-01-01T00:00:00Z",
        update_date="2023-01-01T00:00:00Z",
        owner="test",
        total_items_in_folder=10,
        total_pages_in_folder=None,
        current_page=None,
        items_in_page=None,
        child_objects=None,
    )

    serialized = folder.model_dump()
    assert "total_pages_in_folder" not in serialized
    assert "current_page" not in serialized
    assert "items_in_page" not in serialized
    assert "child_objects" not in serialized

    assert serialized["object_name"] == "Deep Leaf"


def test_serialize_in_order():
    """Test that serialize_in_order enforces a strict structural key order."""
    from app.schemas import FindItemsResponse, FolderMetadata

    folder = FolderMetadata(
        folder_id="123",
        object_name="Deep Leaf",
        object_type="folder",
        folder_path="/root",
        url="https://test",
        creation_date="2023-01-01T00:00:00Z",
        update_date="2023-01-01T00:00:00Z",
        owner="test",
        total_items_in_folder=0,
        total_pages_in_folder=1,
        current_page=1,
        items_in_page=0,
        child_objects=[],
    )

    resp = FindItemsResponse(
        execution_status="success",
        execution_message="Test",
        total_search_matches=1,
        total_pages=1,
        current_page=1,
        items_in_page=1,
        objects_found=[folder],
    )

    serialized = resp.model_dump()
    keys = list(serialized.keys())
    assert keys[0] == "execution_status"
    assert keys[1] == "execution_message"
    assert keys[2] == "total_search_matches"
    assert keys[3] == "total_pages"
    assert keys[4] == "current_page"
    assert keys[5] == "items_in_page"
    assert keys[6] == "objects_found"
