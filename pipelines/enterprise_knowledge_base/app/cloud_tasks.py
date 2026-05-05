import json
from google.cloud import tasks_v2
from loguru import logger
from .document_classification.config import EKB_CONFIG


class CloudTasksService:
    def __init__(self):
        self.client = tasks_v2.CloudTasksClient()
        self.project = EKB_CONFIG.PROJECT_ID
        self.location = EKB_CONFIG.TASKS_LOCATION
        self.queue = EKB_CONFIG.TASKS_QUEUE_ID
        self.queue_path = self.client.queue_path(
            self.project, self.location, self.queue
        )

    def enqueue_ingestion_task(self, job_id: str, payload: dict, service_url: str):
        """
        Creates an HTTP task targeting the Cloud Run /task-handler endpoint.
        """
        url = f"{service_url.rstrip('/')}/task-handler"
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
            hasattr(EKB_CONFIG, "SERVICE_ACCOUNT_EMAIL")
            and EKB_CONFIG.SERVICE_ACCOUNT_EMAIL
        ):
            task["http_request"]["oidc_token"] = {
                "service_account_email": EKB_CONFIG.SERVICE_ACCOUNT_EMAIL
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
