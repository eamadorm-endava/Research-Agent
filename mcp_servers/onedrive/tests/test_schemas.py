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
