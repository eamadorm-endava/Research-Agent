import time
from google.cloud import dlp_v2
from loguru import logger
from .config import EKB_CONFIG


class DLPService:
    """Service class to handle Cloud DLP operations: scanning and de-identification.

    This service is responsible for 'Phase 1' of the classification pipeline,
    identifying high-risk data (Tiers 4 and 5) and polling for results.
    """

    def __init__(self, project_id: str = EKB_CONFIG.PROJECT_ID):
        """Initializes the DLP client using Application Default Credentials (ADC).

        Args:
            project_id (str): The GCP project ID. Defaults to EKB_CONFIG.PROJECT_ID.
        """
        # No explicit credentials passed, uses ADC
        self.client = dlp_v2.DlpServiceClient()
        self.project_id = project_id
        # Use global location for built-in detectors unless regionality is required
        self.parent = f"projects/{project_id}/locations/global"

    def inspect_gcs_file(self, gcs_uri: str) -> str:
        """Triggers a DLP Job to scan a file in GCS for sensitive InfoTypes.

        Args:
            gcs_uri (str): GCS URI of the document (gs://bucket/object).

        Returns:
            str: The full resource name of the created DLP job.
        """
        logger.info(f"Starting DLP scan for: {gcs_uri}")

        inspect_config = {
            "info_types": [{"name": it} for it in EKB_CONFIG.TIER_5_INFOTYPES],
            "custom_info_types": [
                {
                    "info_type": {"name": "TIER_4_KEYWORDS"},
                    "dictionary": {"word_list": {"words": EKB_CONFIG.TIER_4_KEYWORDS}},
                    "likelihood": dlp_v2.Likelihood.VERY_LIKELY,
                }
            ],
            "min_likelihood": dlp_v2.Likelihood.LIKELY,
            "include_quote": False,
        }

        storage_config = {"cloud_storage_options": {"file_set": {"url": gcs_uri}}}

        job_request = {
            "inspect_job": {
                "inspect_config": inspect_config,
                "storage_config": storage_config,
            }
        }

        try:
            response = self.client.create_dlp_job(
                request={
                    "parent": self.parent,
                    "inspect_job": job_request["inspect_job"],
                }
            )
            logger.info(f"DLP Job created: {response.name}")
            return response.name
        except Exception as e:
            logger.error(f"Error starting DLP scan: {str(e)}")
            raise

    def wait_for_job(self, job_name: str, timeout: int = 300) -> list[str]:
        """Polls for job completion and returns the detected high-risk InfoTypes.

        Args:
            job_name (str): Full resource name of the DLP job.
            timeout (int): Maximum seconds to wait.

        Returns:
            list[str]: List of InfoType names detected in the document.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            job = self.client.get_dlp_job(request={"name": job_name})
            state = job.state

            if state == dlp_v2.DlpJob.JobState.DONE:
                findings = []
                stats = job.inspect_details.result.info_type_stats
                for stat in stats:
                    if stat.count > 0:
                        findings.append(stat.info_type.name)
                logger.debug(f"DLP findings detected: {findings}")
                return findings

            if state in (
                dlp_v2.DlpJob.JobState.FAILED,
                dlp_v2.DlpJob.JobState.CANCELED,
            ):
                logger.error(f"DLP Job failed or was canceled: {state.name}")
                raise RuntimeError(f"DLP Job {job_name} failed.")

            logger.debug(f"Waiting for DLP Job... (Current state: {state.name})")
            time.sleep(5)

        raise TimeoutError(
            f"DLP Job {job_name} did not finish within {timeout} seconds."
        )

    def deidentify_gcs_file(self, gcs_uri: str, output_uri: str) -> str:
        """Placeholder for GCS de-identification logic.

        Args:
            gcs_uri (str): Source GCS URI.
            output_uri (str): Destination for masked file.

        Returns:
            str: The URI of the de-identified file.
        """
        logger.info(f"De-identifying file: {gcs_uri}")
        # In a real implementation, this would trigger a de-identification job
        return output_uri
