import pytest
from click import ClickException

from agent.deployment.deploy import parse_key_value_pairs, validate_requirements_file


def test_parse_key_value_pairs_handles_json_list_values():
    parsed = parse_key_value_pairs(
        'PROJECT_ID=test-project,DRIVE_OAUTH_SCOPES=["https://www.googleapis.com/auth/drive.readonly","https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/documents"],GENERAL_TIMEOUT=60'
    )

    assert parsed == {
        "PROJECT_ID": "test-project",
        "DRIVE_OAUTH_SCOPES": '["https://www.googleapis.com/auth/drive.readonly","https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/documents"]',
        "GENERAL_TIMEOUT": "60",
    }


def test_parse_key_value_pairs_handles_multiple_plain_values():
    parsed = parse_key_value_pairs(
        "PROJECT_ID=test-project,REGION=us-central1,DRIVE_ENDPOINT=/mcp"
    )

    assert parsed == {
        "PROJECT_ID": "test-project",
        "REGION": "us-central1",
        "DRIVE_ENDPOINT": "/mcp",
    }


def test_validate_requirements_file_raises_for_missing_file(tmp_path):
    missing_file = tmp_path / "requirements.txt"

    with pytest.raises(ClickException, match="Requirements file not found"):
        validate_requirements_file(str(missing_file))


def test_validate_requirements_file_raises_for_missing_runtime_packages(tmp_path):
    requirements_file = tmp_path / "requirements.txt"
    requirements_file.write_text("pydantic==2.12.5\n", encoding="utf-8")

    with pytest.raises(
        ClickException, match="missing required runtime packages"
    ):
        validate_requirements_file(str(requirements_file))


def test_validate_requirements_file_accepts_agent_runtime_requirements(tmp_path):
    requirements_file = tmp_path / "requirements.txt"
    requirements_file.write_text(
        "google-cloud-aiplatform==1.140.0\ngoogle-adk==1.26.0\n",
        encoding="utf-8",
    )

    validate_requirements_file(str(requirements_file))