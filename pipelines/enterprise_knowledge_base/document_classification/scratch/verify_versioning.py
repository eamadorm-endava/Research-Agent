import sys
import os
import uuid

# Add repository root to sys.path
sys.path.append(os.getcwd())

from pipelines.enterprise_knowledge_base.document_classification.pipeline import (
    ClassificationPipeline,
)
from pipelines.enterprise_knowledge_base.document_classification.schemas import (
    IngestMetadataBQRequest,
)
from pipelines.enterprise_knowledge_base.document_classification.gemini_service.schemas import (
    ContextualClassificationResponse,
)
from pipelines.enterprise_knowledge_base.document_classification.gcs_service.schemas import (
    DocumentMetadata,
)


def verify_versioning():
    print("Initializing Pipeline...")
    pipeline = ClassificationPipeline()

    filename = f"test_versioning_{uuid.uuid4().hex[:8]}.pdf"
    project = "version-test-project"
    gcs_uri = f"gs://kb-it/confidential/{project}/tester/{filename}"

    request = IngestMetadataBQRequest(
        final_original_uri=gcs_uri,
        final_sanitized_uri=None,
        llm_classification=ContextualClassificationResponse(
            final_classification_tier=4,
            confidence=0.95,
            final_domain="it",
            file_description="Versioning test document.",
        ),
        blob_metadata=DocumentMetadata(
            filename=filename,
            mime_type="application/pdf",
            proposed_domain="it",
            project_name=project,
            uploader_email="tester@example.com",
            trust_level="published",
        ),
    )

    print(f"--- Upload 1 for {filename} ---")
    pipeline.ingest_metadata_bq(request)
    print("Upload 1 complete.")

    print(f"--- Upload 2 for {filename} ---")
    # Simulate a re-upload of the same document
    pipeline.ingest_metadata_bq(request)
    print("Upload 2 complete.")

    print("\n--- Verification Query ---")
    # Use bq command to check results
    cmd = f"bq query --use_legacy_sql=false 'SELECT filename, version, latest, classification_tier FROM knowledge_base.documents_metadata WHERE filename = \"{filename}\" ORDER BY version'"
    os.system(cmd)


if __name__ == "__main__":
    verify_versioning()
