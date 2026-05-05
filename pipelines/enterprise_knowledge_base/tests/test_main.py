from unittest.mock import patch
from fastapi.testclient import TestClient
from pipelines.enterprise_knowledge_base.app.main import app
from pipelines.enterprise_knowledge_base.app.schemas import JobStatus, JobStatusResponse

client = TestClient(app)


@patch(
    "pipelines.enterprise_knowledge_base.app.main.cloud_tasks_service.enqueue_ingestion_task"
)
@patch("pipelines.enterprise_knowledge_base.app.main.job_service.create_job")
def test_ingest_document_success(mock_create_job, mock_enqueue_task):
    """
    Test the happy path: the endpoint successfully creates a job
    and returns the processing status.
    """
    # Arrange
    mock_create_job.return_value = "test-job-id"
    request_payload = {"gcs_uri": "gs://landing-zone-bucket/file.pdf"}

    # Act
    response = client.post("/ingest", json=request_payload)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "test-job-id"
    assert data["status"] == "processing"
    assert "File processing task enqueued successfully" in data["message"]

    mock_create_job.assert_called_once_with("file.pdf")


@patch("pipelines.enterprise_knowledge_base.app.main.job_service.create_job")
def test_ingest_document_failure(mock_create_job):
    """
    Test the failure mode: job creation fails.
    """
    # Arrange
    mock_create_job.side_effect = Exception("BQ Write Failure")
    request_payload = {"gcs_uri": "gs://landing-zone-bucket/file.pdf"}

    # Act
    response = client.post("/ingest", json=request_payload)

    # Assert
    assert response.status_code == 500
    assert "Failed to initiate ingestion" in response.json()["detail"]


@patch("pipelines.enterprise_knowledge_base.app.main.job_service.get_job_status")
def test_get_status_success(mock_get_status):
    """
    Test status retrieval for an existing job.
    """
    # Arrange
    mock_get_status.return_value = JobStatusResponse(
        job_id="test-job-id",
        status=JobStatus.SUCCESS,
        message="Finished",
        final_domain="it",
        security_tier="public",
    )

    # Act
    response = client.get("/status/test-job-id")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["final_domain"] == "it"


def test_get_status_not_found():
    """
    Test status retrieval for a non-existent job.
    """
    with patch(
        "pipelines.enterprise_knowledge_base.app.main.job_service.get_job_status",
        return_value=None,
    ):
        response = client.get("/status/invalid-id")
        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"


def test_ingest_document_invalid_payload():
    """
    Test edge cases: invalid GCS URI pattern.
    """
    # Missing gs:// prefix
    response = client.post("/ingest", json={"gcs_uri": "http://invalid.com/file.pdf"})
    assert response.status_code == 422
