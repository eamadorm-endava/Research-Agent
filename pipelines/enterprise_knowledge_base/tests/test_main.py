from unittest.mock import patch

from fastapi.testclient import TestClient

from pipelines.enterprise_knowledge_base.main import app
from pipelines.enterprise_knowledge_base.schemas import OrchestratorRunResponse

client = TestClient(app)


@patch("pipelines.enterprise_knowledge_base.main.KBIngestionPipeline.run")
def test_ingest_document_success(mock_run):
    """
    Test the happy path: the endpoint successfully triggers the orchestrator
    and returns the expected response schema.
    """
    # Arrange
    mock_run.return_value = OrchestratorRunResponse(
        gcs_uri="gs://kb-it/test-project/confidential/jdoe/file.pdf",
        chunks_generated=42,
        final_domain="it",
        security_tier="confidential",
    )

    request_payload = {"gcs_uri": "gs://landing-zone-bucket/file.pdf"}

    # Act
    response = client.post("/ingest", json=request_payload)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["gcs_uri"] == "gs://kb-it/test-project/confidential/jdoe/file.pdf"
    assert data["chunks_generated"] == 42
    assert data["final_domain"] == "it"
    assert data["security_tier"] == "confidential"

    mock_run.assert_called_once()
    run_arg = mock_run.call_args[0][0]
    assert run_arg.gcs_uri == "gs://landing-zone-bucket/file.pdf"


@patch("pipelines.enterprise_knowledge_base.main.KBIngestionPipeline.run")
def test_ingest_document_failure(mock_run):
    """
    Test the failure mode: the orchestrator raises an exception,
    and the endpoint catches it and returns a 500 error.
    """
    # Arrange
    mock_run.side_effect = Exception("Simulated pipeline failure")

    request_payload = {"gcs_uri": "gs://landing-zone-bucket/file.pdf"}

    # Act
    response = client.post("/ingest", json=request_payload)

    # Assert
    assert response.status_code == 500
    assert "Simulated pipeline failure" in response.json()["detail"]


def test_ingest_document_invalid_payload():
    """
    Test edge cases: missing fields in the payload should trigger a 422 Unprocessable Entity.
    """
    # Act: Missing gcs_uri
    response = client.post("/ingest", json={"wrong_key": "value"})

    # Assert
    assert response.status_code == 422
