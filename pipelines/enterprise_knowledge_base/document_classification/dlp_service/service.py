import time
from typing import Union
from google.cloud import dlp_v2
from loguru import logger
from ..config import EKB_CONFIG


class DLPService:
    """Service class to handle Cloud DLP operations: scanning and de-identification.

    This service is responsible for 'Phase 1' of the classification pipeline,
    identifying high-risk data (Tiers 4 and 5) and polling for results.
    """

    def __init__(self, project_id: str = EKB_CONFIG.PROJECT_ID) -> None:
        """Initializes the DLP client using Application Default Credentials (ADC).

        Args:
            project_id (str): The GCP project ID. Defaults to EKB_CONFIG.PROJECT_ID.

        Returns:
            None
        """
        self.client = dlp_v2.DlpServiceClient()
        self.project_id = project_id
        self.parent = f"projects/{project_id}/locations/global"

    def inspect_gcs_file(self, gcs_uri: str) -> str:
        """Triggers a DLP Job to scan a file in GCS for sensitive InfoTypes.
        Detects core PII, dictionary keywords, and document-type patterns.

        Args:
            gcs_uri (str): GCS URI of the document (gs://bucket/object).

        Returns:
            str: The full resource name of the created DLP job.
        """
        logger.info(f"Starting DLP scan for: {gcs_uri}")

        all_info_types = (
            EKB_CONFIG.TIER_5_INFOTYPES
            + EKB_CONFIG.TIER_5_DOCUMENT_TYPES
            + EKB_CONFIG.TIER_4_INFOTYPES
            + EKB_CONFIG.TIER_4_DOCUMENT_TYPES
            + EKB_CONFIG.CONTEXTUAL_INFOTYPES
        )

        inspect_config = {
            "info_types": [{"name": info_type} for info_type in all_info_types],
            "custom_info_types": self._get_custom_keywords_config(),
            "min_likelihood": dlp_v2.Likelihood.LIKELY,
            "include_quote": False,
        }

        storage_config = {"cloud_storage_options": {"file_set": {"url": gcs_uri}}}
        try:
            response = self.client.create_dlp_job(
                request={
                    "parent": self.parent,
                    "inspect_job": {
                        "inspect_config": inspect_config,
                        "storage_config": storage_config,
                    },
                }
            )
            logger.info(f"DLP Job created: {response.name}")
            return response.name
        except Exception as e:
            logger.error(f"Error starting DLP scan: {str(e)}")
            raise

    def wait_for_job(self, job_name: str, timeout: int = 300) -> list[str]:
        """Polls for job completion and returns the detected high-risk InfoTypes.
        Iteratively checks job state until DONE or timeout is reached.

        Args:
            job_name (str): Full resource name of the DLP job.
            timeout (int): Maximum seconds to wait.

        Returns:
            list[str]: List of InfoType names detected in the document.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            dlp_job = self.client.get_dlp_job(request={"name": job_name})
            state = dlp_job.state

            if state == dlp_v2.DlpJob.JobState.DONE:
                findings = [
                    info_type_stat.info_type.name
                    for info_type_stat in dlp_job.inspect_details.result.info_type_stats
                    if info_type_stat.count > 0
                ]
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

        raise TimeoutError(f"DLP Job {job_name} did not finish within {timeout} s.")

    def mask_image_content(
        self, image_bytes: bytes, mime_type: str, requires_context: bool = False
    ) -> bytes:
        """De-identifies sensitive content in images using DLP redact_image API.
        Masks detected findings with solid boxes to prevent data leakage.

        Args:
            image_bytes (bytes): The raw image bytes (PNG/JPEG) to redact.
            mime_type (str): The MIME type of the image.
            requires_context (bool): Instructs to mask contextual PII.

        Returns:
            bytes: The redacted image buffer.
        """
        logger.info(f"Redacting individual image (type: {mime_type})")
        masking_config = self._get_masking_configs(requires_context)

        inspect_config = {
            "info_types": [
                {"name": info_type} for info_type in masking_config["info_types"]
            ],
            "custom_info_types": masking_config["customs"],
            "include_quote": False,
            "min_likelihood": dlp_v2.Likelihood.LIKELY,
        }

        # Build combined redaction configs (built-in + custom)
        redact_configs = [
            {"info_type": {"name": info_type}}
            for info_type in masking_config["info_types"]
        ]
        redact_configs.extend(
            [
                {"info_type": {"name": custom_config["info_type"]["name"]}}
                for custom_config in masking_config["customs"]
            ]
        )

        response = self.client.redact_image(
            request={
                "parent": self.parent,
                "inspect_config": inspect_config,
                "image_redaction_configs": redact_configs,
                "byte_item": {
                    "type_": dlp_v2.ByteContentItem.BytesType.IMAGE,
                    "data": image_bytes,
                },
            }
        )
        return response.redacted_image

    def mask_content(
        self, content: bytes, mime_type: str, requires_context: bool = False
    ) -> bytes:
        """De-identifies sensitive content by replacing findings with InfoType names.
        DlpService.mask_content performs text substitution on ByteContentItems.

        Args:
            content (bytes): The raw content to mask.
            mime_type (str): The MIME type of the content.
            requires_context (bool): If True, also mask purely contextual InfoTypes.

        Returns:
            bytes: The de-identified content buffer.
        """
        logger.info(f"Masking content (type: {mime_type})")
        file_type = self._map_mime_to_dlp_type(mime_type)
        masking_config = self._get_masking_configs(requires_context)

        deid_config = {
            "info_type_transformations": {
                "transformations": [
                    {"primitive_transformation": {"replace_with_info_type_config": {}}}
                ]
            }
        }

        response = self.client.deidentify_content(
            request={
                "parent": self.parent,
                "deidentify_config": deid_config,
                "inspect_config": {
                    "info_types": [
                        {"name": info_type}
                        for info_type in masking_config["info_types"]
                    ],
                    "custom_info_types": masking_config["customs"],
                    "min_likelihood": dlp_v2.Likelihood.LIKELY,
                },
                "item": {"byte_item": {"type_": file_type, "data": content}},
            }
        )
        return response.item.byte_item.data

    def _get_custom_keywords_config(self) -> list[dict]:
        """Provides custom dictionary configs for Tier 4 and Tier 5 keywords.

        Returns:
            list[dict]: List of custom info type configurations.
        """
        logger.debug("Building custom keywords config for inspection.")
        return [
            {
                "info_type": {"name": "TIER_4_KEYWORDS"},
                "dictionary": {"word_list": {"words": EKB_CONFIG.TIER_4_KEYWORDS}},
                "likelihood": dlp_v2.Likelihood.VERY_LIKELY,
            },
            {
                "info_type": {"name": "TIER_5_KEYWORDS"},
                "dictionary": {"word_list": {"words": EKB_CONFIG.TIER_5_KEYWORDS}},
                "likelihood": dlp_v2.Likelihood.VERY_LIKELY,
            },
        ]

    def _get_masking_configs(
        self, requires_context: bool
    ) -> dict[str, Union[list[str], list[dict]]]:
        """Determines the set of info types and customs to use for masking.

        Args:
            requires_context (bool): Whether to include contextual info types.

        Returns:
            dict[str, Union[list[str], list[dict]]]: A dictionary containing
                '"info_types"' (list of strings) and '"customs"' (list of config dicts).
        """
        logger.debug(
            f"Building masking logic into dictionary (contextual: {requires_context})"
        )
        info_types = EKB_CONFIG.TIER_5_INFOTYPES.copy()
        customs = [
            {
                "info_type": {"name": "TIER_5_KEYWORDS"},
                "dictionary": {"word_list": {"words": EKB_CONFIG.TIER_5_KEYWORDS}},
            }
        ]

        if requires_context:
            info_types.extend(EKB_CONFIG.TIER_4_INFOTYPES)
            info_types.extend(EKB_CONFIG.CONTEXTUAL_INFOTYPES)
            customs.append(
                {
                    "info_type": {"name": "TIER_4_KEYWORDS"},
                    "dictionary": {"word_list": {"words": EKB_CONFIG.TIER_4_KEYWORDS}},
                }
            )
        return {"info_types": info_types, "customs": customs}

    def _map_mime_to_dlp_type(self, mime_type: str) -> int:
        """Maps standard MIME types to Cloud DLP ByteContentItem types.

        Args:
            mime_type (str): The MIME string to map.

        Returns:
            int: The DLP BytesType integer mapping.
        """
        logger.debug(f"Mapping MIME type to DLP: {mime_type}")
        if "pdf" in mime_type:
            raise ValueError("DLP deidentify_content does not natively support PDF.")

        if "image" in mime_type:
            return dlp_v2.ByteContentItem.BytesType.IMAGE
        if "text" in mime_type or "json" in mime_type:
            return dlp_v2.ByteContentItem.BytesType.TEXT_UTF8
        return dlp_v2.ByteContentItem.BytesType.BYTES_TYPE_UNSPECIFIED
