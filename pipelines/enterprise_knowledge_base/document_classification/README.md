# EKB Document Classification & Redaction Pipeline (Phase 1)

This service implements **Phase 1** of the Enterprise Knowledge Base (EKB) Dual-Phase Classification Engine. It is an agent-orchestrated component designed to identify high-risk data and enforce the "Mask-First" privacy strategy before contextual AI analysis occurs in Phase 2.

## 1. Role in the EKB Architecture

As defined in the [Enterprise Knowledge Base — Pipeline Architecture Design](https://github.com/eamadorm-endava/Research-Agent/blob/main/docs/Data-Pipelines/Enterprise-Knowledge-Base/Design.md), this component acts as the authoritative security gate between **Step 0: Agent-Driven Ingestion** and **Phase 2: Gemini Classification**.

### The Dual-Phase Engine
| Phase | Engine | Output |
|---|---|---|
| **Phase 1 (Deterministic)** | **Cloud DLP** (This Service) | Tier verdict (4 or 5), DLP findings, `_masked` URI |
| **Phase 2 (Probabilistic)** | **Gemini 2.5 Flash** | Final Tier (1-5), Domain, Summary, Confidence |

## 2. Risk Tier Detection (ISO & NIST Aligned)

The classification system is strictly aligned with **ISO/IEC 27001:2022** (Controls 5.12, 5.13) and **NIST SP 800-53 Rev5**.

### Tier 5: Strictly Confidential (Critical Risk) 🔴🔴
Unauthorized disclosure causes catastrophic harm (Legal, GDPR, existential risk).
- **InfoTypes**: `SSN`, `PASSPORT`, `CREDIT_CARD_NUMBER`, `GCP_API_KEY`.
- **Keywords**: "Termination Agreement", "Severance", "Due Diligence", "Acquisition Target", "Merger Agreement".
- **Action**: **Mandatory Masking** of findings.

### Tier 4: Confidential (High Risk) 🔴
Unauthorized disclosure causes significant competitive or financial harm.
- **InfoTypes**: Strategic markers and financial patterns (`DATE` + `MONEY`).
- **Keywords**: "Confidential", "Proprietary", "Under NDA", "Roadmap", "OKR", "EBITDA", "Q-Plan Targets".
- **Action**: **Mandatory Masking** of findings.

### Tiers 1-3: Public to Client Confidential 🟢🟡🟠
- **Logic**: No hard PII or strategic IP detected.
- **Action**: No masking required. The original URI is passed directly to Phase 2.

## 3. The "Mask-First, Protect-Always" Process

The pipeline manages de-identification to ensure safe downstream AI reasoning while preserving RAG accuracy for authorized users.

### Secure PDF Masking (Split-Redact-Merge)
Since Cloud DLP does not natively redact binary PDF content, we implement the **Split-Redact-Merge** pattern:
1.  **Split**: PDF pages are converted to high-resolution (500 DPI) images to handle small text.
2.  **Redact**: Each image is processed by the Cloud DLP `redact_image` API.
3.  **Merge**: Redacted images are reconstructed into a new, text-free PDF.

### Zero Residuals Policy
- The `_masked` file is a temporary artifact used **only** for Phase 2 analysis.
- After Gemini produces a verdict and the original file is routed to its secured domain bucket, the `_masked` file is **explicitly deleted** from the landing zone.

## 4. Technical Foundations

- **Auth**: Operates under the **delegated OAuth context** of the end-user.
- **Routing**: Successful scans trigger the `KBIngestionPipeline` orchestrator to move files to domain buckets (e.g., `gs://kb-it/`, `gs://kb-hr/`).
- **Standards**: NIST SP 800-171 CUI handling requirements.

## 5. Package Structure

The component is organized into modular service packages, following the project's backend best practices:

```text
document_classification/
├── bq_service/             # BigQuery metadata persistence
│   ├── service.py          # Streaming insert implementation
│   └── schemas.py          # BQMetadataRecord
├── dlp_service/            # Cloud DLP inspection and masking
│   ├── service.py          # Logic for PDF Split-Redact-Merge
│   └── schemas.py          # DLPTriggerResponse
├── gcs_service/            # GCS blob management and metadata extraction
│   ├── service.py          # file routing, copy, and delete helpers
│   └── schemas.py          # DocumentMetadata (GCS attributes)
├── gemini_service/         # Contextual AI classification
│   ├── service.py          # Multimodal Gemini 2.5 Flash reasoning
│   └── schemas.py          # ContextualClassificationResponse
├── config.py               # Shared component configuration
├── pipeline.py             # ClassificationPipeline orchestrator
└── schemas.py              # Orchestrator-level Request/Response models
 ```

 ### Design Principles
 1. **Modular Services**: Each service is self-contained with its own schemas.
 2. **Relative Imports**: Internal communication uses relative imports (`from .gcs_service.service import ...`) limited to one level of depth (`..`).
 3. **Pydantic Validation**: All service boundaries are enforced via Pydantic Request/Response models.
