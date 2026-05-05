import json
from google.cloud import tasks_v2
from loguru import logger
from .config import CLOUD_TASKS_CONFIG
from ..config import EKB_CONFIG

# Global client to share connection pool across multiple requests
task_client = tasks_v2.CloudTasksClient()


class CloudTasksService:
    client = task_client

    def __init__(self):
        self.project = EKB_CONFIG.PROJECT_ID
        self.location = CLOUD_TASKS_CONFIG.TASKS_LOCATION
        self.queue = CLOUD_TASKS_CONFIG.TASKS_QUEUE_ID
        self.queue_path = self.client.queue_path(
            self.project, self.location, self.queue
        )

    def enqueue_ingestion_task(self, job_id: str, payload: dict, service_url: str):
        """
        Creates an HTTP task targeting the Cloud Run /task-handler endpoint.
        """
        url = f"{service_url.rstrip('/')}/task-handler"

        # Cloud Tasks OIDC tokens strictly require HTTPS.
        # Since Cloud Run terminates TLS at the edge, FastAPI often reports the base_url as HTTP.
        if url.startswith("http://") and "localhost" not in url:
            url = url.replace("http://", "https://", 1)
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"job_id": job_id, "request": payload}).encode(),
            }
        }

        # If we have a service account email in config, use OIDC for authenticated invocation
        if (
            hasattr(CLOUD_TASKS_CONFIG, "SERVICE_ACCOUNT_EMAIL")
            and CLOUD_TASKS_CONFIG.SERVICE_ACCOUNT_EMAIL
        ):
            task["http_request"]["oidc_token"] = {
                "service_account_email": CLOUD_TASKS_CONFIG.SERVICE_ACCOUNT_EMAIL
            }

        try:
            response = self.client.create_task(
                request={"parent": self.queue_path, "task": task}
            )
            logger.info(f"Created task {response.name} for job_id: {job_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to create Cloud Task for {job_id}: {e}")
            raise
