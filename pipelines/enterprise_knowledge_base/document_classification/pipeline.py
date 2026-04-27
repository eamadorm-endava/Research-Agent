from typing import Optional
import fitz  # PyMuPDF
import uuid
import unicodedata
from datetime import datetime, timezone
from loguru import logger
from .config import EKB_CONFIG
from .gcs_service.service import GCSService
from .dlp_service.service import DLPService
from .gemini_service.service import GeminiService
from .bq_service.service import BQService
from .gcs_service.schemas import DocumentMetadata
from .dlp_service.schemas import DLPTriggerResponse
from .gemini_service.schemas import ContextualClassificationResponse
from .bq_service.schemas import (
    BQMetadataRecord,
    GetLatestVersionRequest,
    DeprecateVersionsRequest,
)
from .schemas import (
    FileRoutingRequest,
    FileRoutingResponse,
    IngestMetadataBQRequest,
    RunResponse,
)


class ClassificationPipeline:
    """The core logic for Step 01 and Step 02 of the Document Classification Pipeline.

    This class handles metadata extraction, security masking, LLM-based classification,
    and document versioning persistence.
    """

    def __init__(self) -> None:
        """Initializes the required services for classification.

        Returns:
            None
        """
        self.dlp = DLPService()
        self.gcs = GCSService()
        self.gemini = GeminiService()
        self.bq = BQService()

    def run(self, landing_zone_original_uri: str) -> RunResponse:
        """Orchestrates the sequential execution of the classification pipeline.

        Args:
            landing_zone_original_uri (str): The initial URI of the document in GCS.

        Returns:
            RunResponse: Summary of the final classification and routing state.
        """
        logger.info(f"Starting pipeline orchestration for: {landing_zone_original_uri}")
        sanitized_landing_uri: Optional[str] = None

        try:
            # 1. Extract Metadata
            blob_metadata = self._get_blob_metadata(landing_zone_original_uri)

            # 2. DLP Gate
            dlp_resp = self.dlp_trigger(landing_zone_original_uri)
            sanitized_landing_uri = dlp_resp.sanitized_gcs_uri

            # 3. Contextual Classification
            llm_resp = self.contextual_classification(
                sanitized_url=sanitized_landing_uri,
                proposed_classification_tier=dlp_resp.proposed_classification_tier,
                proposed_domain=blob_metadata.proposed_domain,
                trust_level=blob_metadata.trust_level,
            )

            # 4. File Routing
            routing_req = FileRoutingRequest(
                original_landing_uri=landing_zone_original_uri,
                sanitized_landing_uri=sanitized_landing_uri,
                final_domain=llm_resp.final_domain,
                final_security_tier=llm_resp.final_classification_tier,
                project_name=blob_metadata.project_name or "unknown",
                uploader_email=blob_metadata.uploader_email or "unknown",
            )
            routing_resp = self.file_routing(routing_req)

            # 5. Persistence
            persistence_req = IngestMetadataBQRequest(
                final_original_uri=routing_resp.final_original_uri,
                final_sanitized_uri=routing_resp.final_sanitized_uri,
                llm_classification=llm_resp,
                blob_metadata=blob_metadata,
            )
            self.ingest_metadata_bq(persistence_req)

            logger.info(
                f"Pipeline completed successfully for: {landing_zone_original_uri}"
            )
            return RunResponse(
                final_original_uri=routing_resp.final_original_uri,
                final_sanitized_uri=routing_resp.final_sanitized_uri
                or routing_resp.final_original_uri,
                final_security_tier=llm_resp.final_classification_tier,
                final_domain=llm_resp.final_domain,
            )

        except Exception as e:
            logger.error(f"Pipeline failed for {landing_zone_original_uri}: {str(e)}")
            # Cleanup intermediate artifacts if they exist in landing zone
            if (
                sanitized_landing_uri
                and sanitized_landing_uri != landing_zone_original_uri
            ):
                logger.warning(
                    f"Cleaning up intermediate file: {sanitized_landing_uri}"
                )
                try:
                    self.gcs.delete_blob(sanitized_landing_uri)
                except Exception as cleanup_err:
                    logger.error(f"Cleanup failed: {str(cleanup_err)}")
            raise e

    def contextual_classification(
        self,
        sanitized_url: str,
        proposed_classification_tier: Optional[int],
        proposed_domain: Optional[str],
        trust_level: Optional[str],
    ) -> ContextualClassificationResponse:
        """Performs Phase 2 classification using Gemini 2.5 Flash.

        Args:
            sanitized_url (str): URI of the (masked) document to classify.
            proposed_classification_tier (Optional[int]): Tier from Phase 1.
            proposed_domain (Optional[str]): Proposed business domain.
            trust_level (Optional[str]): Maturity level of the doc.

        Returns:
            ContextualClassificationResponse: The final AI classification.
        """
        logger.info(f"Starting contextual classification for: {sanitized_url}")
        metadata = self.gcs.get_blob_metadata(sanitized_url)

        return self.gemini.classify_document(
            gcs_uri=sanitized_url,
            mime_type=metadata.mime_type,
            proposed_tier=proposed_classification_tier,
            proposed_domain=proposed_domain,
            trust_level=trust_level,
        )

    def dlp_trigger(self, landing_zone_original_uri: str) -> DLPTriggerResponse:
        """Triggers DLP scanning and performs masking if high-risk data is found.

        Args:
            landing_zone_original_uri (str): URI of the original document.

        Returns:
            DLPTriggerResponse: The results including the sanitized URI and tier.
        """
        logger.info(f"Triggering DLP scan for: {landing_zone_original_uri}")

        # 1. Scan for findings
        job_name = self.dlp.inspect_gcs_file(landing_zone_original_uri)
        findings = self.dlp.wait_for_job(job_name)

        # 2. Determine risk tier
        tier = self._determine_tier(findings)
        if not tier:
            return DLPTriggerResponse(
                sanitized_gcs_uri=landing_zone_original_uri,
                proposed_classification_tier=None,
            )

        # 3. Apply masking for Tier 4 or 5
        requires_context = tier in [4, 5]
        masked_uri = self._mask_and_save(
            landing_zone_original_uri, requires_context=requires_context
        )
        return DLPTriggerResponse(
            sanitized_gcs_uri=masked_uri, proposed_classification_tier=tier
        )

    def _get_blob_metadata(self, original_uri: str) -> DocumentMetadata:
        """Extracts and returns structured metadata from GCS.

        Args:
            original_uri (str): URI of the original document.

        Returns:
            DocumentMetadata: The structured metadata model.
        """
        logger.debug(f"Extracting metadata for: {original_uri}")
        return self.gcs.get_blob_metadata(original_uri)

    def _determine_tier(self, findings: list[str]) -> Optional[int]:
        """Internal helper to map DLP findings to EKB Tiers."""
        logger.debug(f"Determining risk tier from findings: {findings}")
        if any(
            finding in EKB_CONFIG.TIER_5_INFOTYPES
            or finding in EKB_CONFIG.TIER_5_DOCUMENT_TYPES
            or finding == "TIER_5_KEYWORDS"
            for finding in findings
        ):
            return 5

        if any(
            finding in EKB_CONFIG.TIER_4_DOCUMENT_TYPES
            or finding in EKB_CONFIG.TIER_4_INFOTYPES
            or finding == "TIER_4_KEYWORDS"
            for finding in findings
        ):
            return 4

        return None

    def _mask_pdf_locally(self, original_bytes: bytes, requires_context: bool) -> bytes:
        """Splits PDF into images, redacts via DLP Image API, and merges back."""
        logger.debug("Executing native Split-Redact-Merge on PDF buffer.")
        doc = fitz.open(stream=original_bytes, filetype="pdf")
        redacted_images = []
        try:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pixmap = page.get_pixmap(dpi=300)
                image_buffer = pixmap.tobytes("png")

                masked_img_bytes = self.dlp.mask_image_content(
                    image_buffer, "image/png", requires_context
                )
                redacted_images.append(masked_img_bytes)
        finally:
            doc.close()

        return self._merge_images_to_pdf(redacted_images)

    def _merge_images_to_pdf(self, image_list: list[bytes]) -> bytes:
        """Helper to reconstruct a PDF from sanitized image buffers."""
        logger.debug(f"Merging {len(image_list)} sanitized pages into PDF.")
        output_document = fitz.open()
        try:
            for masked_image in image_list:
                with fitz.open(stream=masked_image, filetype="png") as img_doc:
                    generated_pdf_bytes = img_doc.convert_to_pdf()
                    with fitz.open("pdf", generated_pdf_bytes) as pdf_doc:
                        output_document.insert_pdf(pdf_doc)
            return output_document.write()
        finally:
            output_document.close()

    def _mask_and_save(self, source_uri: str, requires_context: bool = False) -> str:
        """Downloads, masks, and uploads a de-identified copy of the source."""
        logger.debug(f"Applying masking to: {source_uri} (Context: {requires_context})")
        # Create a unique intermediate path in the landing zone
        filename_parts = source_uri.rsplit(".", 1)
        base_name = filename_parts[0]
        ext = f".{filename_parts[1]}" if len(filename_parts) > 1 else ""

        # Add a unique execution ID to the intermediate file name
        execution_id = str(uuid.uuid4())[:8]
        masked_uri = f"{base_name}_{execution_id}_masked{ext}"

        document_metadata = self.gcs.get_blob_metadata(source_uri)
        try:
            original_bytes = self.gcs.download_blob_bytes(source_uri)
            if "pdf" in document_metadata.mime_type:
                masked_bytes = self._mask_pdf_locally(original_bytes, requires_context)
            else:
                masked_bytes = self.dlp.mask_content(
                    original_bytes, document_metadata.mime_type, requires_context
                )

            return self.gcs.upload_blob_bytes(
                masked_uri, masked_bytes, content_type=document_metadata.mime_type
            )
        except Exception as e:
            logger.error(f"Redaction failed: {str(e)}")
            raise e

    def file_routing(self, request: FileRoutingRequest) -> FileRoutingResponse:
        """Routes the original and masked files to the domain-specific bucket."""
        logger.info(
            f"Routing files for domain: {request.final_domain}, Tier: {request.final_security_tier}"
        )
        tier_label = EKB_CONFIG.TIER_TO_LABEL.get(
            request.final_security_tier, "unknown"
        )
        filename = request.original_landing_uri.split("/")[-1]
        uploader_prefix = request.uploader_email.split("@")[0]

        dest_base = f"gs://kb-{request.final_domain}/{request.project_name}/{tier_label}/{uploader_prefix}/"
        final_original_uri = f"{dest_base}{filename}"

        # 1. Copy Original
        self.gcs.copy_blob(request.original_landing_uri, final_original_uri)

        # 2. Copy Masked (if exists)
        final_sanitized_uri = None
        if (
            request.sanitized_landing_uri
            and request.sanitized_landing_uri != request.original_landing_uri
        ):
            sanitized_filename = request.sanitized_landing_uri.split("/")[-1]
            final_sanitized_uri = f"{dest_base}{sanitized_filename}"
            self.gcs.copy_blob(request.sanitized_landing_uri, final_sanitized_uri)

        # 3. Cleanup Landing Zone
        self.gcs.delete_blob(request.original_landing_uri)
        if (
            request.sanitized_landing_uri
            and request.sanitized_landing_uri != request.original_landing_uri
        ):
            self.gcs.delete_blob(request.sanitized_landing_uri)

        return FileRoutingResponse(
            final_original_uri=final_original_uri,
            final_sanitized_uri=final_sanitized_uri,
        )

    def ingest_metadata_bq(self, request: IngestMetadataBQRequest) -> bool:
        """Persists the document metadata into BQ with versioning logic.

        Args:
            request (IngestMetadataBQRequest): The metadata and classification context.

        Returns:
            bool: True if insertion was successful.
        """
        logger.info(
            f"Persisting versioned metadata to BQ for: {request.final_original_uri}"
        )

        # 1. Generate Deterministic ID
        project_id = request.blob_metadata.project_name or "unknown"
        filename = request.blob_metadata.filename
        gcs_uri = request.final_original_uri

        doc_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, unicodedata.normalize("NFC", gcs_uri))
        )

        # 2. Handle Versioning
        version_req = GetLatestVersionRequest(document_id=doc_id)
        version_resp = self.bq.get_latest_version(version_req)

        if version_resp.current_version > 0:
            logger.info(
                f"Found existing version {version_resp.current_version}. Deprecating..."
            )
            self.bq.deprecate_old_versions(DeprecateVersionsRequest(document_id=doc_id))
            new_version = version_resp.current_version + 1
        else:
            new_version = 1

        # 3. Map Tier to Label
        tier_int = request.llm_classification.final_classification_tier
        tier_label = EKB_CONFIG.TIER_TO_LABEL.get(tier_int, f"tier-{tier_int}")

        record = BQMetadataRecord(
            document_id=doc_id,
            gcs_uri=gcs_uri,
            filename=filename,
            classification_tier=tier_label,
            domain=request.llm_classification.final_domain,
            confidence_score=request.llm_classification.confidence,
            trust_level=request.blob_metadata.trust_level or "unknown",
            project_id=project_id,
            uploader_email=request.blob_metadata.uploader_email or "unknown",
            description=request.llm_classification.file_description,
            version=new_version,
            latest=True,
            ingested_at=datetime.now(timezone.utc).isoformat(),
        )

        return self.bq.insert_metadata(record)
