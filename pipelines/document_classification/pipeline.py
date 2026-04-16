import os
import fitz  # PyMuPDF
from loguru import logger
from .config import EKB_CONFIG
from .dlp_service import DLPService
from .gcs_service import GCSService


class ClassificationPipeline:
    """The core logic for Step 01 of the Document Classification Pipeline.

    This class is stateless and handles metadata extraction and security masking
    using Cloud DLP and GCS. It adheres to the 60-line method limit.
    """

    def __init__(self):
        """Initializes the required services."""
        self.dlp = DLPService()
        self.gcs = GCSService()

    def _get_blob_metadata(self, landing_zone_original_uri: str) -> dict:
        """Extracts and returns the 8 required metadata fields from GCS.

        Args:
            landing_zone_original_uri (str): URI of the original document.

        Returns:
            dict: The extracted metadata (filename, mime_type, domain, etc.)
        """
        logger.debug(f"Extracting metadata for: {landing_zone_original_uri}")
        return self.gcs.get_blob_metadata(landing_zone_original_uri)

    def dlp_trigger(self, landing_zone_original_uri: str) -> dict:
        """Triggers DLP scanning and performs masking if high-risk data is found.

        Args:
            landing_zone_original_uri (str): URI of the original document.

        Returns:
            dict: {"sanitized_gcs_uri": str, "proposed_classification_tier": int or None}
        """
        logger.info(f"Triggering DLP scan for: {landing_zone_original_uri}")

        # 1. Scan for findings
        job_name = self.dlp.inspect_gcs_file(landing_zone_original_uri)
        findings = self.dlp.wait_for_job(job_name)

        # 2. Determine risk tier
        tier = self._determine_tier(findings)
        if not tier:
            return {
                "sanitized_gcs_uri": landing_zone_original_uri,
                "proposed_classification_tier": None,
            }

        # 3. Apply masking for Tier 4 or 5
        requires_context = tier in [4, 5]
        masked_uri = self._mask_and_save(
            landing_zone_original_uri, requires_contextual_masking=requires_context
        )
        return {"sanitized_gcs_uri": masked_uri, "proposed_classification_tier": tier}

    def _determine_tier(self, findings: list[str]) -> int:
        """Internal helper to map DLP findings to EKB Tiers.

        Args:
            findings (list[str]): List of detected InfoTypes.

        Returns:
            int: 4, 5, or None.
        """
        if any(
            f in EKB_CONFIG.TIER_5_INFOTYPES or f in EKB_CONFIG.TIER_5_DOCUMENT_TYPES
            for f in findings
        ):
            return 5

        if (
            any(f in EKB_CONFIG.TIER_4_DOCUMENT_TYPES for f in findings)
            or "TIER_4_KEYWORDS" in findings
        ):
            return 4

        return None

    def _mask_and_save(
        self, source_uri: str, requires_contextual_masking: bool = False
    ) -> str:
        """Internal helper to download, mask, and upload a de-identified copy.

        Args:
            source_uri (str): URI of the original document.
            requires_contextual_masking (bool): Instructs to mask contextual PII.

        Returns:
            str: URI of the masked document.
        """

    def _mask_pdf_locally(
        self, original_bytes: bytes, requires_contextual_masking: bool
    ) -> bytes:
        """Splits PDF into images, redacts via DLP Image API, and merges back to PDF.
        Follows the Split-Redact-Merge pattern for secure PDF de-identification.

        Args:
            original_bytes (bytes): The raw PDF bytes.
            requires_contextual_masking (bool): Whether to mask contextual PII.

        Returns:
            bytes: The redacted PDF bytes.
        """
        logger.debug("Executing native Split-Redact-Merge on PDF buffer.")
        doc = fitz.open(stream=original_bytes, filetype="pdf")

        redacted_images = []
        try:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap()
                img_bytes = pix.tobytes("png")

                # Send single page to DLP Image Redactor
                masked_img_bytes = self.dlp.mask_image_content(
                    img_bytes, "image/png", requires_contextual_masking
                )
                redacted_images.append(masked_img_bytes)
        finally:
            doc.close()

        # Merge back to PDF natively
        out_doc = fitz.open()
        try:
            for masked_img in redacted_images:
                with fitz.open(stream=masked_img, filetype="png") as img_doc:
                    pdf_bytes = img_doc.convert_to_pdf()
                    with fitz.open("pdf", pdf_bytes) as pdf_doc:
                        out_doc.insert_pdf(pdf_doc)
            return out_doc.write()
        finally:
            out_doc.close()

    def _mask_and_save(
        self, source_uri: str, requires_contextual_masking: bool = False
    ) -> str:
        logger.debug(
            f"Applying masking to: {source_uri} (Context: {requires_contextual_masking})"
        )

        # 1. Prepare paths
        base_name, ext = os.path.splitext(source_uri)
        masked_uri = f"{base_name}_masked{ext}"

        # 2. Download and try synchronous mask
        meta = self.gcs.get_blob_metadata(source_uri)
        try:
            original_bytes = self.gcs.download_blob_bytes(source_uri)

            if "pdf" in meta["mime_type"]:
                masked_bytes = self._mask_pdf_locally(
                    original_bytes, requires_contextual_masking
                )
            else:
                masked_bytes = self.dlp.mask_content(
                    original_bytes, meta["mime_type"], requires_contextual_masking
                )

            # 3. Upload masked copy synchronously
            return self.gcs.upload_blob_bytes(
                masked_uri, masked_bytes, content_type=meta["mime_type"]
            )
        except Exception as e:
            logger.error(f"Redaction failed: {str(e)}")
            raise e
