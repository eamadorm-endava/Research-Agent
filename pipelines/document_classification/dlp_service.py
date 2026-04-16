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

        # Combine all explicit info_types for scanning
        all_info_types = (
            EKB_CONFIG.TIER_5_INFOTYPES
            + EKB_CONFIG.TIER_5_DOCUMENT_TYPES
            + EKB_CONFIG.TIER_4_DOCUMENT_TYPES
            + EKB_CONFIG.CONTEXTUAL_INFOTYPES
        )

        inspect_config = {
            "info_types": [{"name": it} for it in all_info_types],
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
                logger.info(f"DLP findings detected: {findings}")
                return findings

            if state in (
                dlp_v2.DlpJob.JobState.FAILED,
                dlp_v2.DlpJob.JobState.CANCELED,
            ):
                logger.error(f"DLP Job failed or was canceled: {state.name}")
                raise RuntimeError(f"DLP Job {job_name} failed.")

            logger.info(f"Waiting for DLP Job... (Current state: {state.name})")
            time.sleep(5)

        raise TimeoutError(
            f"DLP Job {job_name} did not finish within {timeout} seconds."
        )

    def mask_image_content(
        self,
        image_bytes: bytes,
        mime_type: str,
        requires_contextual_masking: bool = False,
    ) -> bytes:
        """De-identifies sensitive content in images using DLP redact_image API.

        Args:
            image_bytes (bytes): The raw image bytes (PNG/JPEG) to redact.
            mime_type (str): The MIME type of the image.
            requires_contextual_masking (bool): Instructs to mask contextual PII.

        Returns:
            bytes: The redacted image buffer.
        """
        logger.debug(f"Redacting individual image (type: {mime_type})")

        file_type = dlp_v2.ByteContentItem.BytesType.IMAGE

        masking_info_types = EKB_CONFIG.TIER_5_INFOTYPES.copy()
        if requires_contextual_masking:
            masking_info_types.extend(EKB_CONFIG.CONTEXTUAL_INFOTYPES)

        inspect_config = {
            "info_types": [{"name": it} for it in masking_info_types],
            "custom_info_types": [
                {
                    "info_type": {"name": "TIER_4_KEYWORDS"},
                    "dictionary": {"word_list": {"words": EKB_CONFIG.TIER_4_KEYWORDS}},
                }
            ],
            "include_quote": False,
        }

        # We don't specify explicit ImageRedactionConfigs.
        # By default, DLP will redact all findings in the InspectConfig with an opaque box.
        image_redaction_configs = []
        for info_type in masking_info_types:
            image_redaction_configs.append({"info_type": {"name": info_type}})

        image_redaction_configs.append({"info_type": {"name": "TIER_4_KEYWORDS"}})

        response = self.client.redact_image(
            request={
                "parent": self.parent,
                "inspect_config": inspect_config,
                "image_redaction_configs": image_redaction_configs,
                "byte_item": {"type_": file_type, "data": image_bytes},
            }
        )
        return response.redacted_image

    def mask_content(
        self, content: bytes, mime_type: str, requires_contextual_masking: bool = False
    ) -> bytes:
        """De-identifies sensitive content by replacing findings with InfoType names.

        Args:
            content (bytes): The raw content to mask.
            mime_type (str): The MIME type of the content.
            requires_contextual_masking (bool): If True, also mask purely contextual
                InfoTypes (like Names, Emails). Otherwise, only mask Core Tier 5 items.

        Returns:
            bytes: The de-identified content.
        """
        logger.info(f"Masking content (type: {mime_type})")

        # 1. Map MIME to DLP BytesType
        if "pdf" in mime_type:
            raise ValueError(
                f"Google Cloud DLP deidentify_content API does not natively support inline binary redaction for {mime_type}."
            )

        file_type = dlp_v2.ByteContentItem.BytesType.BYTES_TYPE_UNSPECIFIED
        if "image" in mime_type:
            file_type = dlp_v2.ByteContentItem.BytesType.IMAGE
        elif "text" in mime_type or "json" in mime_type:
            file_type = dlp_v2.ByteContentItem.BytesType.TEXT_UTF8

        # 2. Configure de-identification
        deid_config = {
            "info_type_transformations": {
                "transformations": [
                    {"primitive_transformation": {"replace_with_info_type_config": {}}}
                ]
            }
        }

        masking_info_types = EKB_CONFIG.TIER_5_INFOTYPES.copy()
        if requires_contextual_masking:
            masking_info_types.extend(EKB_CONFIG.CONTEXTUAL_INFOTYPES)

        inspect_config = {
            "info_types": [{"name": it} for it in masking_info_types],
            "custom_info_types": [
                {
                    "info_type": {"name": "TIER_4_KEYWORDS"},
                    "dictionary": {"word_list": {"words": EKB_CONFIG.TIER_4_KEYWORDS}},
                }
            ],
        }

        # 3. Execute
        response = self.client.deidentify_content(
            request={
                "parent": self.parent,
                "deidentify_config": deid_config,
                "inspect_config": inspect_config,
                "item": {"byte_item": {"type_": file_type, "data": content}},
            }
        )
        return response.item.byte_item.data
