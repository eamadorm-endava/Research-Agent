# Enterprise Knowledge Base — Pipeline Architecture Design

> **Status:** Draft — Approved by Architecture / Data Engineering Team  
> **Version:** 2.0  
> **Last Updated:** 2026-04-15  
> **Owner:** Data Engineering Team  
> **Standards Alignment:** ISO/IEC 27001:2022 (Controls 5.12, 5.13), NIST SP 800-53 Rev5 (AC-16, RA-2, SI-12), NIST SP 800-171 Rev3 (§3.1, §3.13), NIST SP 800-60 Vol 1–2  

---

## 1. Overview & Goals

The **Enterprise Knowledge Base (EKB)** is a fully automated, event-driven data pipeline designed to:

1. **Ingest**: Direct user interaction via **Gemini Enterprise AI Agent**. The user uploads a file and provides metadata (Project, PII status) to an **ADK-powered Skill**.
2. **Handoff**: The Agent writes to the shared GCS landing zone with enriched metadata.
3. **Classify**: Automated document vetting via **Cloud DLP + Gemini LLM** (overriding user claims if necessary).
4. **Route**: Document is moved to domain-specific, access-controlled GCS buckets.
5. **Extract**: Structured metadata lands in BigQuery for searching.
6. **Enrich**: BQML-powered summary generation.
7. **Vectorize**: Semantic indexing via BigQuery ML Vector Search.

---

## 2. High-Level Architecture

```mermaid
flowchart TD
    subgraph AGENT["1 AI Agent Entry Point"]
        Z["User Uploads File to Chat"] --> Y["Gemini Agent (ADK Skill)"]
        Y --> X["Metadata Collection (Project?, PII?)"]
        X --> B["GCS: kb-landing-zone"]
    end

    subgraph INGEST["2 Automated Ingestion"]
        B --> C["Eventarc Trigger (object.finalize)"]
    end

    subgraph CLASSIFY["3 Classification — CloudRun"]
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

    subgraph VECTOR["4 Vectorization (RAG)"]
        K --> N["BigQuery ML: ML.GENERATE_EMBEDDING"]
        N --> O["BigQuery VECTOR_SEARCH"]
        O --> P["AI Agent MCP Servers: semantic_search tool"]
    end
```

---

## 3. Step 0: Agent-Driven Ingestion (Human-in-the-Loop)

The primary entry point for documents is a direct interaction with the **Enterprise AI Agent** in chat.

### Ingestion Flow:
1.  **File Upload**: User attaches a PDF/Docx to the chat.
2.  **Skill Activation**: The Agent triggers the **`Ingestion Metadata Skill` (ADK-based)**.
3.  **Questionnaire**: The Agent dynamically asks for:
    - **Project ID**: Which team or project owns this document? (**Note**: The Skill must perform a **Similarity Check** against existing BigQuery metadata to suggest existing project names and prevent duplicates like `ProjectAlpha` vs `Project-Alpha`).
    - **PII Intent**: "Does this document contain sensitive PII (SSNs, CCs)?" (Optional pre-classification).
    - **Trust Maturity**: Is this a **Published** document or a **WIP** draft?
4.  **GCS Handoff**: The Agent writes the file to the Landing Zone, mapping conversation slots to object metadata (`x-goog-meta-project`, etc.).

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

**[ISO/IEC 27001:2022](https://www.iso.org/standard/27001)** ([Control 5.12](https://www.iso.org/standard/75652.html)) requires organizations to define a classification scheme proportional to their risk posture, categorizing information by **business value, sensitivity, legal obligations, and the potential impact of unauthorized disclosure**. The standard mandates that each classification level translate directly into defined handling and protection requirements ([Control 5.13](https://www.iso.org/standard/75652.html) — Labelling).

**[NIST SP 800-53 Rev5](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final)** maps this to **[FIPS 199](https://csrc.nist.gov/pubs/fips/199/final) impact levels**: every information type must be assessed as **Low**, **Moderate**, or **High** impact based on the consequence of a confidentiality breach. This impact level drives which security controls apply.

**[NIST SP 800-171 Rev3](https://csrc.nist.gov/pubs/sp/800/171/r3/final)** introduces **[Controlled Unclassified Information (CUI)](https://www.archives.gov/cui)** — data requiring safeguarding per law, regulation, or government policy without carrying formal classified status. In a corporate context, client NDA data, internal HR records, financial forecasts, and M&A intelligence all map to CUI-equivalent sensitivity requiring restricted access, audit logging, and transmission controls.

The five-tier model below synthesizes these frameworks into a practical enterprise classification scheme, with each tier mapped to its international standard equivalent.

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
- Can **upgrade** a tier if business-context signals are detected (e.g., a document without hard PII that describes employee termination terms → Tier 5).
- Produces **tier, domain selection, document summary**, and **confidence score** as structured outputs.

> [!IMPORTANT]
> **Masking Requirement (Issue #107):** For **Tier 4** and **Tier 5** documents, Cloud DLP **must** execute a de-identification transformation. The masked document is stored in GCS with a `_masked` suffix. The pipeline returns the **URI of the masked document** (`masked_gcs_uri`) for all downstream processing. The original unmasked file is retained in the domain bucket, protected by CMEK + IAM Conditions, and recorded as `source_uri` in BigQuery.

### 5.3 Classification Matrix

| Tier | Label | FIPS 199 Impact | ISO 27001:2022 Analogue | Risk Level | Definition & Rationale | Standards Alignment | Phase 1 — DLP InfoTypes (Deterministic) | Phase 2 — Gemini Signals (Probabilistic) | Masking |
|---|---|---|---|---|---|---|---|---|---|
| **1** | **Public** | Low | *Public* | 🟢 None | Information **approved for external release**. Unauthorized disclosure causes no measurable organizational harm. Examples: press releases, marketing collateral, published documentation, open-source code. | **ISO 27001 §5.12**: Lowest label — no confidentiality controls required. Classification exists only to confirm intentional public release. **NIST SP 800-53 AC-16**: Security attribute = public. **FIPS 199**: Low confidentiality impact. | None required. DLP runs in scan-only mode. Detection of public markers: Custom `KEYWORD` — *"For Public Release"*, *"Press Release"*, *"Public Statement"*. No sensitive InfoTypes present. | Tone is outward-facing. No client/internal jargon, proprietary references, or internal identifiers. Phase 2 confirms absence of all higher-tier signals. Assigns Tier 1 only when no ambiguity exists. | None |
| **2** | **Internal Use Only** | Low | *Internal* | 🟡 Low | Information intended **exclusively for internal employees**. Unauthorized disclosure causes limited reputational harm but no legal or compliance violation. Examples: all-hands presentations, internal SOPs, onboarding guides, corporate wikis, internal newsletters. | **ISO 27001 §5.12**: *"Internal"* label. Requires basic access controls (authenticated users only) but no encryption mandate. **NIST SP 800-53 RA-2**: Low-impact information type. **NIST SP 800-60**: Mission/business process support information with Low confidentiality impact. | Custom `KEYWORD` — *"Internal Only"*, *"Not for External Distribution"*, *"All Hands"*, *"Company Confidential — Internal"*, company intranet domain names. No PII or financial InfoTypes. | Detects internal distribution lists, org chart references, SOP/policy language, and internal project names. Confirms document is internal-facing. Rejects upgrade to Tier 3+ unless client/strategic signals are found. | None |
| **3** | **Client Confidential** | Moderate | *Confidential* | 🟠 Moderate–High | Information pertaining to **specific named clients under contractual obligation (NDA, MSA, SOW)**. Unauthorized disclosure constitutes a breach of contract and creates legal liability. Examples: client SOWs, engagement letters, project deliverables marked Confidential, client-specific architecture diagrams, delivery milestones. | **ISO 27001 §5.12**: *"Confidential"* label. Requires access controls limited to named individuals/groups + audit logging. **NIST SP 800-171 §3.1**: CUI handling — data shared with a third party under agreement requiring protection. **NIST SP 800-53 AC-16**: Moderate security attributes for controlled data. **FIPS 199**: Moderate confidentiality impact. | Custom `KEYWORD` — *"Statement of Work"*, *"NDA"*, *"Non-Disclosure"*, *"Milestone"*, *"Deliverable"*, *"Engagement Letter"*, *"MSA"*. Known client name dictionary (extensible). Person names co-occurring with external company names. | Detects named client entities, contractual language, financial amounts tied to deliverables, and third-party identity references. Assigns Tier 3 when client scope is clear but no hard PII or strategic IP is present. Can upgrade to Tier 4 if strategic roadmap context is detected alongside client content. | None |
| **4** | **Confidential** | High | *Restricted* | 🔴 High | Sensitive **internal strategic and proprietary information**. Unauthorized disclosure could cause significant competitive harm, financial loss, or regulatory violation. Examples: product roadmaps, internal M&A strategy (early stage), Q-plan financial forecasts, proprietary algorithms, partner agreements, OKR targets, pricing models. | **ISO 27001 §5.12**: *"Restricted"* (or upper-confidential) label — strictest access controls enforced by role and need-to-know. **NIST SP 800-53 RA-2**: High-impact confidentiality. **NIST SP 800-171 §3.13**: CUI — restricted access, encrypted transmission, and audit logging required. **NIST SP 800-53 SI-12**: Information retention and protection obligations. **FIPS 199**: High confidentiality impact. | Built-in: `DATE` + `MONEY` in proximity (financial forecast pattern). Custom `KEYWORD` — *"Confidential"*, *"Proprietary"*, *"Under NDA"*, *"Roadmap"*, *"OKR"*, *"EBITDA"*, *"Q1 Target"*, *"Q2 Target"*, *"Q3 Target"*, *"Q4 Target"*, project codenames. `ORGANIZATION_NAME` in strategic planning context. | Detects strategic framing: business strategy language, proprietary methodology, financial projection context, competitive intelligence. Upgrades from Tier 3 when multiple strategic signals co-occur. Downgrades to Tier 3 if content is client-only with no internal IP. | **YES** — DLP de-identifies, stores `<filename>_masked.<ext>` in GCS, returns `masked_gcs_uri` |
| **5** | **Strictly Confidential** | High | *Strictly Confidential* | 🔴🔴 Critical | **Need-to-know basis only.** Unauthorized disclosure causes catastrophic harm: severe legal liability (GDPR, CCPA, HIPAA), individual harm, or existential organizational risk. Examples: HR records with PII, employee PIPs/termination agreements, severance packages, M&A due diligence files, financial data with government identifiers, system credentials. | **ISO 27001 §5.12**: Highest classification level — equivalent to *"Strictly Confidential"*. Maximum security controls: CMEK, MFA, strict IAM, VPC-SC. **NIST SP 800-53 AC-16 + SI-12**: Maximum security attribute enforcement and retention controls. **NIST SP 800-171 §3.1 + §3.13**: CUI-Specified — most sensitive categories: HR (Privacy CUI), Legal, Financial. **GDPR Art. 9 / CCPA §1798.100**: Personal data requiring mandatory protection. **FIPS 199**: High confidentiality impact. | **Identity PII**: `US_SOCIAL_SECURITY_NUMBER`, `PASSPORT`, `DRIVERS_LICENSE_NUMBER`. **Financial PII**: `CREDIT_CARD_NUMBER`, `IBAN_CODE`, `SWIFT_CODE`. **Credentials**: `GCP_API_KEY`, `JSON_WEB_TOKEN`, `AUTH_TOKEN`. **HR/Legal Custom** `KEYWORD` — *"Performance Improvement Plan"*, *"PIP"*, *"Termination Agreement"*, *"Severance"*, *"Due Diligence"*, *"Acquisition Target"*, *"Merger Agreement"*. | Detects M&A due diligence language, acquisition strategy, employee performance management context, termination/severance framing, and bankruptcy risk language. **Contextual Tier 5 is assigned** when HR/legal business context signals appear **even without hard PII** (e.g., a document describing employee termination terms without SSNs). Phase 2 is the sole authority for contextual Tier 5 elevation. | **YES** — DLP de-identifies, stores `<filename>_masked.<ext>` in GCS, returns `masked_gcs_uri` |

### 5.4 Masking Pipeline for Tiers 4 & 5

When **Phase 1 (DLP)** detects Tier 4 or Tier 5 content, the following masking workflow executes **before Phase 2**:

```
1. DLP inspects the document and confirms Tier 4 or Tier 5 InfoType findings.
2. DLP executes a de-identification (InfoType transformation: MASK or REPLACE_WITH_INFO_TYPE).
3. Masked document is stored in the SAME GCS bucket as the original, with the _masked suffix:
   gs://<domain>/<tier>/<project>/<uploader>/<filename>_masked.<ext>
4. The masked_gcs_uri is returned to the classification pipeline.
5. Phase 2 (Gemini 2.5 Flash) reads ONLY the masked document via multimodal GCS access.
6. BigQuery metadata records:
   - gcs_uri     → masked_gcs_uri (safe for downstream access)
   - source_uri  → original document URI (restricted, audit-only)
7. The original document remains protected by CMEK + strict IAM Conditions (need-to-know only).
```

> [!WARNING]
> The pipeline **never** passes raw Tier 4/5 content to the Gemini model. Gemini always operates on the `masked_gcs_uri`. This enforces a DLP-first security gate that ensures AI models cannot inadvertently expose or memorize sensitive PII or strategic data.

### 5.5 Standards Compliance Summary

| Standard | Relevant Control | How the Tier System Complies |
|---|---|---|
| **[ISO/IEC 27001:2022](https://www.iso.org/standard/27001)** | [Control 5.12 — Information Classification](https://www.iso.org/standard/75652.html) | Five tiers defined by business value, legal obligations, and impact of unauthorized disclosure. Each tier maps directly to a standard classification label (Public → Restricted). |
| **[ISO/IEC 27001:2022](https://www.iso.org/standard/27001)** | [Control 5.13 — Labelling of Information](https://www.iso.org/standard/75652.html) | Every document receives a `classification_tier` metadata tag stored in BigQuery (`classification_tier` field) and as a GCS object metadata attribute for routing. |
| **[ISO/IEC 27002:2022](https://www.iso.org/standard/75652.html)** | §5.12 Implementation Guidance | Risk-proportionate protection: Tiers 1–2 → IAM access control; Tier 3 → audit logging + contract-scoped IAM; Tiers 4–5 → IAM + CMEK + DLP masking + VPC-SC. |
| **[NIST SP 800-53 Rev5](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final)** | [AC-16 — Security Attributes](https://csrc.nist.gov/projects/cprt/catalog#/cprt/framework/version/SP_800_53_5_1_1/home?element=AC-16) | `classification_tier` is the security attribute applied to every information object at write time, driving IAM condition enforcement. |
| **[NIST SP 800-53 Rev5](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final)** | [RA-2 — Security Categorization](https://csrc.nist.gov/projects/cprt/catalog#/cprt/framework/version/SP_800_53_5_1_1/home?element=RA-2) | Tiers 1–2 map to [FIPS 199](https://csrc.nist.gov/pubs/fips/199/final) **Low**, Tier 3 to **Moderate**, Tiers 4–5 to **High** confidentiality impact. |
| **[NIST SP 800-53 Rev5](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final)** | [SI-12 — Information Management & Retention](https://csrc.nist.gov/projects/cprt/catalog#/cprt/framework/version/SP_800_53_5_1_1/home?element=SI-12) | Masking enforces data minimization: downstream systems only access the masked copy. `source_uri` is retained for authorized audit and recovery. |
| **[NIST SP 800-171 Rev3](https://csrc.nist.gov/pubs/sp/800/171/r3/final)** | [§3.1 — Access Control](https://csrc.nist.gov/pubs/sp/800/171/r3/final) | GCS IAM Conditions (prefix-based) enforce need-to-know access per tier for CUI-equivalent data (Tiers 3–5). |
| **[NIST SP 800-171 Rev3](https://csrc.nist.gov/pubs/sp/800/171/r3/final)** | [§3.13 — System & Communications Protection](https://csrc.nist.gov/pubs/sp/800/171/r3/final) | CMEK on all buckets + VPC-SC boundary protects CUI in transit and at rest. DLP masking ensures Tier 4–5 data is never transmitted in raw form to downstream services. |
| **[GDPR Art. 9](https://gdpr-info.eu/art-9-gdpr/) / [CCPA §1798.100](https://oag.ca.gov/privacy/ccpa)** | Personal Data Protection | Tier 5 masking ensures AI models process only de-identified data, satisfying data minimization and purpose limitation principles. |



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
- **Why Tier First?**: IAM Conditions do not support wildcards (e.g., `*/strictly-confidential/*`). By placing the `{tier}` at the **root prefix**, we can grant classification-based access (e.g., "The Security Group can view all `strictly-confidential` data across all projects") using a single, scalable condition.
- **Ownership Boundary**: Placing `{uploader_email_prefix}` in the path satisfies the **ADR-001** requirement for user-level authorization boundaries, allowing for per-user access policies if needed.
- **Uniform Bucket-Level Access (UBLA)**: This architecture **requires** UBLA to be enabled to bypass ACL legacy overrides.

### Routing Design: No Quarantine Bucket

> [!NOTE]
> **All documents are always routed to their domain bucket** — no quarantine bucket exists. A document is never withheld from storage based on classifier confidence.

**Rationale:** The purpose of BigQuery metadata is to provide an auditable, queryable record of every document and its classification outcome, including the `confidence_score`. Low-confidence results are surfaced through BigQuery queries rather than physical isolation. This approach provides several advantages:

- **No data loss:** Documents with uncertain classification (e.g., borderline Tier 2/3) are still stored and accessible.
- **Human-in-the-loop review via BQ:** Operators can query `WHERE confidence_score < 0.75` to identify documents requiring manual review and reclassification.
- **Audit trail integrity:** Every document ingested has a complete, unbroken lifecycle record in BigQuery from `ingested_at` through `routed_at`.
- **Correctability:** Since the classification tier is stored as metadata in BQ and as a GCS path prefix, a document can be re-routed to the correct tier prefix if the classification is later revised — without data loss.



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
| `creator_name` | `STRING` | Extracted doc property |
| `ingested_at` | `TIMESTAMP` | Time arrived in landing zone |
| `routed_at` | `TIMESTAMP` | Time moved to domain bucket |
| `description` | `STRING` | **AI Summary (Generated via BQML)** |
| `vectorization_status`| `STRING` | pending, completed, failed |

### 7.1 Performance & Cost Optimization (Partitioning & Clustering)

To maximize query efficiency and reduce BigQuery analysis costs (GCP Slot usage), the `kb_metadata` table is configured as follows:

- **Partitioning**: Day-partitioned by `ingested_at`. This allows for efficient time-series analysis and "hot data" filtering.
- **Clustering**: Multi-column clustering by `domain`, `project`, `classification_tier`, `uploader_email`.

**Benefits**:
1. **Cost Savings**: BigQuery only scans data segments that match the filters (e.g., `WHERE project = 'alpha'`), significantly reducing the amount of bytes processed.
2. **Speed**: Dramatically faster retrieval for RAG-anchored queries that filter by team or security tier.
3. **Audit Readiness**: Queries for a specific user's activity (`uploader_email`) are highly optimized.

---

## 8. Vector Database Payload (BigQuery ML Vector Search)

Each chunk index carries a rich metadata payload for grounding responses:

```json
{
  "id": "doc_uuid_chunk_001",
  "embedding": [0.012, -0.83, ...],
  "metadata": {
    "document_id": "doc_uuid",
    "filename": "file.pdf",
    "domain": "it",
    "tier": "confidential",
    "trust_level": "published",
    "project": "alpha",
    "description": "Short AI-generated summary...",
    "chunk_text": "The actual text context of this segment..."
  }
}
```

---

## 9. Google Cloud Services — Selection & Justification

| Step | Service | Justification |
|---|---|---|
| **Entry Point** | **Gemini Enterprise Agent** | Direct human interface for ingestion in Chat. |
| **Ingestion Logic** | **ADK (Skill Framework)** | Simplifies the bridge between user intent (metadata collection) and GCS storage. |
| **Compute Engine** | **Agent Engine** | Secure environment for running ADK-powered Skills. |
| **Trigger** | **Eventarc** | Decoupled eventing. Supports object finalization events with low latency. |
| **Compute** | **Cloud Run** | Single service handles the full classify-and-persist flow: DLP scan → Gemini classification → BigQuery write → GCS routing. |
| **Phase 1 Classifier** | **Cloud DLP** | Hardened, enterprise-grade PII and InfoType detection. Mandatory gate for Tier 4/5 masking before AI processing. |
| **Phase 2 Classifier** | **Gemini 2.5 Flash (Vertex AI)** | Multimodal GCS access enables reasoning over document content. Produces `tier`, `domain`, `summary`, and `confidence_score` as structured output — this output is the metadata record written to BigQuery. |
| **Metadata Store** | **BigQuery** | Receives the structured output from the classifier directly. No intermediate extractor job required. Highly scalable for audit queries and RAG-anchored filtering. |
| **Vector DB** | **BigQuery + BQML** | Leverages existing metadata in BigQuery. VECTOR_SEARCH() + ML.GENERATE_EMBEDDING() minimizes infrastructure and scales natively within SQL. |

---

## 10. Data Privacy & ADR-001 Alignment

The EKB pipeline is built to strictly adhere to **[ADR-001: Data Privacy Strategy](https://github.com/eamadorm-endava/Research-Agent/blob/main/docs/ADRs/001-Data-Privacy-Strategy.md)**.

> [!IMPORTANT]
> **V2.0 Behaviour Change — Tiers 4 & 5:** The original *"Preserve-and-Protect"* strategy for Tiers 4 & 5 has been superseded by a **"Mask-First, Protect-Always"** model per Issue #107 and ISO/IEC 27001:2022 Control 5.12. For Tier 4 and Tier 5 documents, Cloud DLP **must** produce a masked copy, store it in GCS, and return the `masked_gcs_uri`. All downstream AI and metadata services operate on the masked URI. The original unmasked document is retained under CMEK and strict IAM Conditions for auditing only.

- **Mask-First (Tiers 4–5):** DLP de-identification is mandatory before any downstream service (including Gemini 2.5 Flash) processes the document. BigQuery records `gcs_uri = masked_gcs_uri` and `source_uri = original_uri`. Only authorized principals with explicit IAM grants may access `source_uri`.
- **Preserve-and-Protect (Tiers 1–3):** For lower-sensitivity tiers, original documents are processed directly by Phase 2. No masking is applied. IAM Conditions and CMEK provide adequate protection at these levels.
- **Encryption at Rest (CMEK):** All GCS Buckets and BigQuery Datasets **must** be encrypted with Customer-Managed Encryption Keys. This applies to both original and masked document versions.
- **DLP as Security Gate:** Cloud DLP is the **mandatory first step** in the classification pipeline. Its InfoType findings determine tier assignment for Tiers 4 and 5. For Tiers 1–3, DLP provides supplementary pattern evidence to the Gemini contextual classifier.

---

## 11. Next Steps

1. **Phase 0 (Infrastructure)**: Provision GCS Buckets (`kb-landing-zone` + domain buckets) and BigQuery Dataset/`kb_metadata` table. Ensure DLP, Gemini, and GCS service accounts have correct IAM bindings.
2. **Phase 1 — Landing Zone**: Set up `gs://kb-landing-zone` and Eventarc trigger (`object.finalize`) pointing to the Classifier Cloud Run service.
3. **Phase 1 — DLP Scanning Service** *(Issue #107)*: Implement Python-based Cloud DLP scanning. Deterministic InfoType scan for Tiers 4 & 5. Automatic de-identification when triggered. Masked document stored in GCS with `_masked` suffix. Returns `(tier, masked_gcs_uri | original_gcs_uri)`. InfoTypes managed via `config.py`.
4. **Phase 2 — Gemini Classifier + BQ Write** *(User Story — Gemini 2.5 Flash)*: Gemini 2.5 Flash reads the safest available URI via multimodal GCS access. Returns structured output `(tier, domain, summary, confidence_score)`. The **same Cloud Run service** immediately writes this record to BigQuery `kb_metadata` — no separate extractor job needed. The `summary` field from Gemini replaces the previous BQML description generation step.
5. **Phase 3 — Routing**: Router moves the document from `kb-landing-zone` to the correct domain bucket (`gs://kb-<domain>/<tier>/<project>/<uploader>/<filename>`).
6. **Phase 4 (Vectorization RAG)**: Vectorization pipeline — BigQuery ML (VECTOR_SEARCH + ML.GENERATE_EMBEDDING).

---

## 12. Deferred Scope & Known Limitations

### 12.1 KMS / CMEK — Not Implemented in Phase 1

> [!NOTE]
> **Customer-Managed Encryption Keys (CMEK) via Cloud KMS are explicitly deferred and will not be implemented in the first stage of this pipeline.**

Although this document references CMEK across multiple sections (data privacy, ADR-001 alignment, standards compliance), its implementation is a significant infrastructure dependency that requires a dedicated Cloud KMS setup, key ring configuration, and IAM key binding on all buckets and BigQuery datasets.

**Current approach (Phase 1):** GCS Buckets and BigQuery Datasets will use Google-managed default encryption. This is sufficient to launch the pipeline and satisfies the functional requirements for classification and metadata storage.

**Future milestone:** CMEK will be provisioned as a dedicated infrastructure phase once the core classification pipeline is validated in production. At that point:
- A Cloud KMS key ring will be created per environment (dev/staging/prod).
- All GCS domain buckets and `kb-landing-zone` will be re-created or migrated with CMEK enforced.
- The BigQuery `kb_metadata` dataset will be configured with the CMEK key.
- References in this document and ADR-001 to CMEK will reflect the active implementation.

All other security controls described in this document (IAM Conditions, VPC-SC, DLP masking) remain in scope for Phase 1.
