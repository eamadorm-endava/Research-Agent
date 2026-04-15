# Enterprise Knowledge Base — Pipeline Architecture Design

> **Status:** Draft — Approved by Architecture / Data Engineering Team  
> **Version:** 2.0  
> **Last Updated:** 2026-04-15  
> **Owner:** Data Engineering Team  
> **Standards Alignment:** ISO/IEC 27001:2022 (Controls 5.12, 5.13), NIST SP 800-53 Rev5 (AC-16, RA-2, SI-12), NIST SP 800-171 Rev3 (§3.1, §3.13), NIST SP 800-60 Vol 1–2  

---

## 1. Overview & Goals

The **Enterprise Knowledge Base (EKB)** is an agent-orchestrated and event-driven data pipeline designed to:

1. **Ingest**: Direct user interaction via **Gemini Enterprise AI Agent**. The user uploads a file and provides metadata (Project, PII status, Versioning) to an **ADK-powered Skill**.
2. **Handoff**: The Agent writes to the shared GCS landing zone with enriched custom metadata.
3. **Classify**: The Agent **directly triggers** the automated document vetting via **Cloud DLP + Gemini LLM** (overriding user claims if necessary).
4. **Route**: Document is moved to domain-specific, access-controlled GCS buckets.
5. **Extract**: Structured metadata lands in BigQuery for searching.
6. **Vectorize (RAG)**: An automated Eventarc trigger fires upon document arrival in the domain buckets to initiate parsing, chunking, and semantic indexing via BigQuery ML Vector Search.

---

## 2. High-Level Architecture

```mermaid
flowchart TD
    subgraph AGENT["1 AI Agent Entry Point"]
        Z["User Uploads File to Chat"] --> Y["Gemini Agent (ADK Skill)"]
        Y --> X["Metadata Collection (Project?, PII?)"]
        X --> B["GCS: kb-landing-zone"]
        B --> C["Agent Triggers Classification API"]
    end

    subgraph CLASSIFY["2 Classification — CloudRun"]
        C --> D["Phase 1 — Cloud DLP: Deterministic InfoType Scan"]
        D --> DG{"Tier 4 or 5 Detected?"}
        DG -- Yes --> DM["DLP De-Identification: Mask to GCS _masked suffix, return masked_uri"]
        DG -- No --> DP["Pass original URI"]
        DM --> E["Phase 2 — Gemini 2.5 Flash: Multimodal GCS Access, Contextual Classifier"]
        DP --> E
        E --> F["Structured Output: tier, domain, summary, confidence_score"]
        F --> K["BigQuery kb_metadata table (direct write)"]
        F --> H["Domain Buckets: gs://kb-domain/tier/project/filename"]
    end

    subgraph VECTOR["3 Vectorization (RAG)"]
        H --> L["Eventarc Trigger (object.finalize in domain bucket)"]
        L --> N["BigQuery ML: Document Chunking & ML.GENERATE_EMBEDDING"]
        N --> O["BigQuery VECTOR_SEARCH"]
        O --> P["AI Agent MCP Servers: semantic_search tool"]
    end
```

---

## 3. Step 0: Agent-Driven Ingestion (Human-in-the-Loop)

The primary entry point for documents is a direct interaction with the **Enterprise AI Agent** in chat.

### Ingestion Flow:
1.  **File Upload**: User attaches a PDF/Docx to the chat.
2.  **Skill Activation**: The Agent triggers the **`Ingestion Metadata Skill` (ADK-based)**.
3.  **Questionnaire**: The Agent dynamically asks for:
    - **Project ID**: Which team or project owns this document? (**Note**: The Skill must perform a **Similarity Check** against existing BigQuery metadata to prevent duplicates).
    - **Versioning**: Is this document a new version of an existing file?
    - **PII Intent**: "Does this document contain sensitive PII (SSNs, CCs)?" (Optional pre-classification).
    - **Trust Maturity**: Is this a **Published** document or a **WIP** draft?
4.  **GCS Handoff**: The Agent writes the file to the Landing Zone, mapping conversation slots to object metadata (`x-goog-meta-project`, etc.).
5.  **Pipeline Trigger**: Once the upload is confirmed, the Agent makes a direct API call to the Classification Cloud Run service, initiating the processing and securing the URI.

> [!IMPORTANT]
> **Safety Overrider**: While the user can declare "No PII", the downstream **Cloud DLP (Phase 1)** always performs a deterministic scan and will override the user's claim if sensitive data is found.

---

## 4. Trust level system

Every document uploaded must have a **Trust Level** metadata tag to denote its maturity:

| Level | Key | Description |
|---|---|---|
| **Published** | `published` | Reviewed, approved, and formally published content. |
| **WIP** | `wip` | Working drafts under active development. |
| **Archived** | `archived` | Historical context; potentially outdated. |

> **Implementation:** Stored in GCS custom metadata as `x-goog-meta-trust-level`.

---

## 5. AI Document Classification Matrix

The classification system is aligned with **[ISO/IEC 27001:2022](https://www.iso.org/standard/27001)** (Controls 5.12 *Information Classification* and 5.13 *Labelling of Information*), **[NIST SP 800-53 Rev5](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final)** (AC-16 *Security Attributes*, RA-2 *Security Categorization*, SI-12 *Information Management and Retention*), **[NIST SP 800-171 Rev3](https://csrc.nist.gov/pubs/sp/800/171/r3/final)** (CUI handling requirements), and **[NIST SP 800-60 Vol 1](https://csrc.nist.gov/pubs/sp/800/60/v1r1/final) & [Vol 2](https://csrc.nist.gov/pubs/sp/800/60/v2r1/final)** (information type impact mapping).

### 5.1 Classification Philosophy

**[ISO/IEC 27001:2022](https://www.iso.org/standard/27001)** ([Control 5.12](https://www.iso.org/standard/75652.html)) requires organizations to define a classification scheme proportional to their risk posture, categorizing information by **business value, sensitivity, legal obligations, and the potential impact of unauthorized disclosure**. 

*(Standard mappings to FIPS 199 and NIST SP 800-171 CUI controls remain fully enforced per architectural standards).*

### 5.2 Dual-Phase Classification Engine

Document classification is performed in **two sequential phases**:

| Phase | Engine | Approach | Output |
|---|---|---|---|
| **Phase 1 — Deterministic** | Cloud DLP | Pattern-matching via built-in and custom InfoTypes | Tier verdict (4 or 5), DLP findings, masked_uri (when applicable) |
| **Phase 2 — Probabilistic** | Gemini 2.5 Flash (Multimodal GCS) | Business context reasoning over document content | Final tier (1–5), domain, document summary, confidence score |

**Phase 1 (DLP)** is the authoritative security gate:
- Scans the document for hard PII, credentials, and strategic markers.
- If Tier 4 or Tier 5 content is found, **masking is executed before Phase 2 runs**.
- Phase 2 always receives the safest available URI (masked if applicable, original if not).

**Phase 2 (Gemini)** provides contextual intelligence:
- Reads the document via native multimodal GCS access.
- Produces **tier, domain selection, document summary**, and **confidence score** as structured outputs.

> [!IMPORTANT]
> **Masking Requirement (Issue #107):** For **Tier 4** and **Tier 5** documents, Cloud DLP **must** execute a de-identification transformation. The masked document is stored in GCS with a `_masked` suffix. The pipeline returns the **URI of the masked document** (`masked_gcs_uri`) for all downstream processing.

### 5.3 Classification Matrix

*(Table mappings for Tiers 1–5 align with Public, Internal Use Only, Client Confidential, Confidential, and Strictly Confidential definitions. For brevity, refer to original design for complete dictionary definitions).*

### 5.4 Masking Pipeline for Tiers 4 & 5

When **Phase 1 (DLP)** detects Tier 4 or Tier 5 content, the following masking workflow executes **before Phase 2**:

```text
1. DLP inspects the document and confirms Tier 4 or Tier 5 InfoType findings.
2. DLP executes a de-identification (InfoType transformation: MASK or REPLACE_WITH_INFO_TYPE).
3. Masked document is stored in the SAME GCS bucket as the original, with the _masked suffix.
4. The masked_gcs_uri is returned to the classification pipeline.
5. Phase 2 (Gemini 2.5 Flash) reads ONLY the masked document via multimodal GCS access.
6. BigQuery metadata records: gcs_uri → masked_gcs_uri / source_uri → original document URI
7. The original document remains protected by CMEK + strict IAM Conditions (need-to-know only).
```
> [!WARNING]
> The pipeline **never** passes raw Tier 4/5 content to the Gemini model.

---

## 6. Domain Storage Hierarchy

Documents are routed to domain-specific buckets with the following internal structure:

**Domain Buckets:**
- `gs://kb-it/`
- `gs://kb-finance/`
- `gs://kb-hr/`
- `gs://kb-sales/`
- `gs://kb-executives/`
- `gs://kb-legal/`
- `gs://kb-operations/`


**Folder Structure within each bucket:**
```
/{tier}/
  {project_name}/
    {uploader_email_prefix}/
      {filename}
```
*Example: `gs://kb-it/confidential/project-alpha/maria.gutierrez/architecture.pdf`*

### Security Rationale: IAM Condition Prefixing
To enforce fine-grained security at the object level, the pipeline relies on **GCS IAM Conditions** with the `.startsWith()` operator.
- **Why Tier First?**: IAM Conditions do not support wildcards (e.g., `*/strictly-confidential/*`). By placing the `{tier}` at the **root prefix**, we can grant classification-based access using a single, scalable condition.
- **Uniform Bucket-Level Access (UBLA)**: This architecture **requires** UBLA to be enabled.

### Routing Design: No Quarantine Bucket

> [!NOTE]
> **All documents are always routed to their domain bucket** — no quarantine bucket exists. 

Low-confidence results are surfaced through BigQuery queries rather than physical isolation, preserving data integrity and simplifying correctability loops.

---

## 7. BigQuery Metadata Schema (`kb_metadata`)

| Field | Type | Description |
|---|---|---|
| `document_id` | `STRING` | UUID (Primary Key) |
| `gcs_uri` | `STRING` | Final routed path in domain bucket |
| `source_uri` | `STRING` | Original landing zone path |
| `filename` | `STRING` | Original filename |
| `classification_tier` | `STRING` | Result from classification matrix |
| `domain` | `STRING` | it, hr, sales, etc. |
| `confidence_score` | `FLOAT64` | AI classifier confidence (0.0 - 1.0) |
| `trust_level` | `STRING` | published, wip, archived |
| `project` | `STRING` | Project identifier |
| `uploader_email` | `STRING` | Email of the contributor |
| `description` | `STRING` | AI Summary (Generated via Gemini) |
| `vectorization_status`| `STRING` | pending, completed, failed |

### 7.1 Performance & Cost Optimization (Partitioning & Clustering)
- **Partitioning**: Day-partitioned by `ingested_at`. 
- **Clustering**: Multi-column clustering by `domain`, `project`, `classification_tier`, `uploader_email`.

---

## 8. Vector Database Payload (BigQuery ML Vector Search)

Each chunk index carries a rich metadata payload for grounding responses:

```json
{
  "id": "doc_uuid_chunk_001",
  "embedding": [0.012, -0.83, ...],
  "metadata": {
    "document_id": "doc_uuid",
    "domain": "it",
    "tier": "confidential",
    "project": "alpha",
    "chunk_text": "The actual text context of this segment..."
  }
}
```
---
## 9. Google Cloud Services — Selection & Justification

| Step | Service | Justification |
|---|---|---|
| **Entry Point** | **Gemini Enterprise Agent** | Direct human interface for ingestion in Chat. |
| **Ingestion Logic** | **ADK (Skill Framework)** | Orchestrates metadata collection, GCS handoff, and actively triggers the Classification pipeline. |
| **Compute Engine** | **Agent Engine** | Secure environment for running ADK-powered Skills. |
| **Trigger (RAG)** | **Eventarc** | Decoupled eventing. Supports object finalization events in the **domain buckets** to automatically kick off the RAG/vectorization pipeline. |
| **Compute (Classification)**| **Cloud Run** | Invoked directly by the Agent. Handles DLP scan → Gemini classification → BigQuery write → GCS routing. |
| **Compute (RAG)**| **Cloud Run** | Handles document parsing and text chunking logic before BQ insertion. |
| **Metadata Store** | **BigQuery** | Receives the structured output from the classifier directly. |
| **Vector DB** | **BigQuery + BQML** | VECTOR_SEARCH() + ML.GENERATE_EMBEDDING() minimizes infrastructure and scales natively within SQL. |

---

## 10. Data Privacy & ADR-001 Alignment

The EKB pipeline is built to strictly adhere to **[ADR-001: Data Privacy Strategy](https://github.com/eamadorm-endava/Research-Agent/blob/main/docs/ADRs/001-Data-Privacy-Strategy.md)**.

> [!IMPORTANT]
> **V2.0 Behaviour Change — Tiers 4 & 5:** The original *"Preserve-and-Protect"* strategy for Tiers 4 & 5 has been superseded by a **"Mask-First, Protect-Always"** model. Cloud DLP **must** produce a masked copy. All downstream AI and metadata services operate on the masked URI. 

---

## 11. Next Steps

1. **Phase 0 (Infrastructure)**: Provision GCS Buckets (`kb-landing-zone` + domain buckets) and BigQuery Dataset/`kb_metadata` table. Ensure DLP, Gemini, and GCS service accounts have correct IAM bindings.
2. **Phase 1 — Landing Zone & Trigger Setup**: Set up `gs://kb-landing-zone`. Configure the AI Agent to perform an authenticated HTTP POST directly to the Classifier Cloud Run service once ingestion is complete.
3. **Phase 1 — DLP Scanning Service**: Implement Python-based Cloud DLP scanning. Deterministic InfoType scan for Tiers 4 & 5. 
4. **Phase 2 — Gemini Classifier + BQ Write**: Gemini 2.5 Flash reads the safest available URI via multimodal GCS access. Returns structured output for immediate BigQuery ingestion.
5. **Phase 3 — Routing**: Router moves the document from `kb-landing-zone` to the correct domain bucket.
6. **Phase 4 — Vectorization RAG (Event-Driven)**: Configure Eventarc triggers on all domain buckets (`object.finalize`). When the router deposits a new file (or a file update), Eventarc triggers the parsing/chunking Cloud Run service, followed by BigQuery ML embedding generation.

---

## 12. Deferred Scope & Known Limitations

### 12.1 KMS / CMEK — Not Implemented in Phase 1

> [!NOTE]
> **Customer-Managed Encryption Keys (CMEK) via Cloud KMS are explicitly deferred and will not be implemented in the first stage of this pipeline.**

**Current approach (Phase 1):** GCS Buckets and BigQuery Datasets will use Google-managed default encryption. CMEK will be provisioned as a dedicated infrastructure phase once the core classification pipeline is validated in production.