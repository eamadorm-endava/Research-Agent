import uuid
from loguru import logger
from .config import EKB_CONFIG
from .dlp_service import DLPService
from .llm_service import LLMService
from .bq_service import BQService
from .gcs_service import GCSService


class ClassificationPipeline:
    """The main orchestrator for the Enterprise Knowledge Base (EKB) document classification.

    Coordinates the multi-stage logic: DLP safety scanning, LLM contextual analysis,
    BigQuery metadata logging, and GCS physical routing.
    """

    def __init__(self):
        """Initializes all required service components."""
        self.dlp = DLPService()
        self.llm = LLMService()
        self.bq = BQService()
        self.gcs = GCSService()

    def run(self, source_uri: str) -> dict:
        """Executes the full classification and routing pipeline for a document.

        Args:
            source_uri (str): The landing zone GCS URI (gs://bucket/object).

        Returns:
            dict: The final classification and metadata results.
        """
        logger.info(f"--- Starting EKB Pipeline for: {source_uri} ---")

        base_meta = self.gcs.get_blob_metadata(source_uri)
        doc_id = str(uuid.uuid4())

        # Phase 1 & 2: Security & Analysis
        enrichment = self._analyze_document(source_uri, base_meta)

        # Route & Log
        final_tier = enrichment.get("tier", "1—public")
        domain = enrichment.get("domain", "it")

        routed_uri = self._route_document(source_uri, base_meta, domain, final_tier)

        bq_record = self._create_bq_record(
            doc_id, routed_uri, source_uri, base_meta, enrichment
        )

        self.bq.insert_document_metadata(bq_record)

        logger.info(f"--- Pipeline completed successfully for {doc_id} ---")
        return bq_record

    def _analyze_document(self, source_uri: str, base_meta: dict) -> dict:
        """Internal helper to coordinate DLP and LLM analysis.
        Polls for DLP results and maps findings to EKB Tiers 4 or 5 if detected.

        Args:
            source_uri (str): Source URI.
            base_meta (dict): Base metadata from GCS.

        Returns:
            dict: Enrichment data from the Gemini LLM.
        """
        logger.debug(f"Analyzing security for: {source_uri}")

        # 1. Start DLP Job and Wait
        job_name = self.dlp.inspect_gcs_file(source_uri)
        findings = self.dlp.wait_for_job(job_name)

        # 2. Determine Tier based on findings
        detected_tier = None
        if any(f in EKB_CONFIG.TIER_5_INFOTYPES for f in findings):
            detected_tier = "5—strictly-confidential"
        elif "TIER_4_KEYWORDS" in findings:
            detected_tier = "4—confidential"

        # 3. Handle Masking for Tiers 4/5
        llm_input_uri = source_uri
        if detected_tier:
            logger.info(f"Risk detected ({detected_tier}). Applying guardrails.")
            llm_input_uri = self.dlp.deidentify_gcs_file(source_uri, source_uri)

        # 4. Contextual Classification
        return self.llm.classify_and_summarize(
            gcs_uri=llm_input_uri,
            mime_type=base_meta["content_type"],
            known_tier=detected_tier,
        )

    def _route_document(
        self, source_uri: str, meta: dict, domain: str, tier: str
    ) -> str:
        """Internal helper to move file to the correct domain bucket.

        Args:
            source_uri (str): Original URI.
            meta (dict): Metadata.
            domain (str): Target domain.
            tier (str): Target tier.

        Returns:
            str: Final routed URI.
        """
        logger.debug(f"Routing document to domain: {domain}")
        path_tier = tier.split("—")[-1].strip().lower().replace(" ", "-")
        dest_bucket = f"kb-{domain}"
        uploader = meta["uploader_email"].split("@")[0]
        dest_path = f"{path_tier}/{meta['project']}/{uploader}/{meta['filename']}"

        dest_uri = f"gs://{dest_bucket}/{dest_path}"

        try:
            return self.gcs.move_blob(source_uri, dest_uri)
        except Exception as e:
            logger.error(f"Error moving file: {str(e)}")
            return source_uri

    def _create_bq_record(
        self, doc_id: str, uri: str, src: str, meta: dict, enr: dict
    ) -> dict:
        """Internal helper to document the BigQuery row.

        Args:
            doc_id (str): UUID. [truncated]
            uri (str): Final URI.
            src (str): Source URI.
            meta (dict): Metadata.
            enr (dict): Enrichment.

        Returns:
            dict: The BQ-ready dictionary.
        """
        return {
            "document_id": doc_id,
            "gcs_uri": uri,
            "source_uri": src,
            "filename": meta["filename"],
            "classification_tier": enr.get("tier", "1—public"),
            "domain": enr.get("domain", "it"),
            "confidence_score": 0.95,
            "trust_level": meta["trust_level"],
            "project": meta["project"],
            "uploader_email": meta["uploader_email"],
            "creator_name": "Unknown",
            "description": enr.get("description", "No description"),
            "vectorization_status": "pending",
        }


if __name__ == "__main__":
    # Example execution via CLI
    import sys

    if len(sys.argv) > 1:
        pipeline = ClassificationPipeline()
        pipeline.run(sys.argv[1])
