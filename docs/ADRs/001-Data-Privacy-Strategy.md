# ADR-001: Data Privacy Strategy for Gemini Enterprise Agents and Services

**Status**: Proposed
**Date**: March 11, 2026
**Owner**: Data Engineering / Infrastructure
**Related Systems**: Google Drive, Google Calendar, GCS, BigQuery, Gemini Enterprise, Cloud DLP, Cloud KMS, IAM, Cloud Logging

## 1. Context
Gemini Enterprise AI Agents will consume enterprise data from multiple sources, primarily:

- Google Drive documents such as meeting transcripts, Recordings, Docs
- Google Calendar metadata such as meeting details, dates, and participants
- Google Cloud Storage unstructured data
- BigQuery structured datasets
- Other custom enterprise inputs

A core business requirement is that AI Agents must have access to highly accurate, unmasked data so they can preserve business context and provide useful answers. At the same time, the platform must ensure strong privacy, security, compliance, and least-privilege access.

A key challenge is that aggressive masking or irreversible DLP transformations may remove critical context from meeting transcripts and other business documents. This would reduce the quality and usefulness of AI-generated results.

The project context also indicates that some meeting transcripts may initially reside in personal Google Drives of sales team members, rather than a centrally managed Shared Drive. Therefore, the privacy strategy must support secure ingestion from Google Drive while preserving per-user authorization boundaries.

## 2. Decision
The platform will adopt a secure access model instead of a permanent masking model.

The selected strategy is:

- Preserve original document content for AI consumption
- Use strict IAM boundaries and user-context propagation to control which documents can be retrieved
- Use Cloud KMS / CMEK for encryption at rest
- Use Cloud DLP primarily for inspection, classification, and tagging, not masking of source content and demasking in target services
- Use tokenization only for selected structured fields, not for primary transcript content
- Ensure audit logs and telemetry do not leak raw sensitive content

## 3. Decision Drivers
This decision is based on the following drivers:

- AI Agents need full business context to produce accurate output
- Meeting transcripts and contracts lose meaning when masked information
- User-specific authorization boundaries must be preserved end-to-end
- Security controls must be enforceable across Drive, Calendar, GCS, BigQuery, and Agent retrieval
- Logs and observability must not become a secondary channel for PII leakage
- The design must remain practical for engineering teams to implement and operate

## 4. Evaluated Options
### Option A. Permanently mask or redact sensitive content before AI consumption

**Pros**

- Reduces exposure of raw PII at rest
- Can simplify some audit concerns

**Cons**

- High risk of permanently losing business context
- Reduces transcript usefulness for AI
- May break names, project references, and relationship context
- Not suitable when the AI must reason on exact meeting content

**Decision**
Rejected as primary strategy.

### Option B. Preserve original content and protect it with IAM, encryption, and secure retrieval

**Pros**

- Preserves document fidelity and AI usefulness
- Aligns with least-privilege access model
- Better fits enterprise documents and transcript use cases
- Allows DLP to classify data without destroying it

**Cons**

- Requires stronger access architecture
- Requires careful audit/log redaction controls
- Requires robust identity propagation

**Decision**
Accepted as primary strategy.

### Option C. Tokenize all sensitive values before AI consumption

**Pros**

- Reduces direct exposure of identifiers
- Useful for certain structured datasets

**Cons**

- Poor fit for free-text transcripts
- Damages natural-language context
- Requires detokenization layer and mapping store
- Increases operational complexity

**Decision**
Use selectively only for narrow structured use cases, not for main transcript content.

## 5. Chosen Privacy Strategy by Control Area
### 5.1 Cloud DLP
Cloud DLP will be used for:

- Discovery of sensitive content
- Classification of documents by sensitivity
- Metadata tagging
- Policy routing for downstream handling
- Optional redaction of logs or derived low-trust outputs

Cloud DLP will not be used as the default mechanism to permanently redact source documents before AI consumption.

**Rationale:**
The business requirement explicitly prioritizes highly accurate, unmasked meeting data. DLP inspection supports governance without destroying source context.

Example metadata tags:

- contains_pii=true
- sensitivity=confidential
- data_source=drive
- owner_user_id=<user_id>
- project_id=<project_id>

### 5.2 Cloud KMS
All stored enterprise content in GCS and BigQuery will use Cloud KMS managed by Google to encrypt the information

Cloud KMS will provide:

- Encryption at rest
- Centralized key management
- Key rotation
- Key access auditing
- Separation of duties between data storage and key administration

### 5.3 Encryption in Transit
All communications between source systems, ETL services, GCS, BigQuery, and Gemini-related services must use secure transport. This includes:

- API calls:
    - HTTPS
    - TLS (for sensitive information or if required by user)
- Google internal encrypted service-to-service communication where applicable
- Private connectivity when feasible for internal services

### 5.4 IAM and User Authorization Boundary
IAM is the primary privacy boundary.

The design principle is:

- The AI Agent must only retrieve documents that the invoking end-user is already authorized to read.

This will be enforced using user impersonation / context propagation. Retrieval requests must carry the invoking user identity or an equivalent authorization context, and all document access decisions must be evaluated against that identity.

This is especially important because source files may exist in personal drives, where access is user-specific and not inherently centralized.

### 5.5 Tokenization
Tokenization is optional and limited to structured data scenarios such as:

- client identifiers
- contract IDs
- account numbers
- structured reference fields

Tokenization is not recommended for meeting transcripts, or other free-text documents because it materially harms semantic understanding.

### 5.6 Logging and Telemetry Privacy
The platform will not store raw document content, raw transcript text, or sensitive prompt payloads in normal operational logs.

Logs should prefer:

- document IDs
- event IDs
- request IDs
- user IDs or service principals where necessary
- decision metadata such as “access granted/denied”
- sensitivity labels, not raw content

Where there is risk of accidental content logging, apply redaction or DLP inspection to logging pipelines.

## 6. Recommended Data Source Handling
### 6.1 Google Drive
For Google Drive, the preferred enterprise model is:

- Use Shared Drives where possible for better centralized management
- If the organization must read from personal drives, use delegated user authorization or OAuth-based access that respects the file owner’s permissions
- Do not flatten all Drive content into a broad service account access model unless explicitly approved and tightly scoped

For synchronized storage in GCS, preserve metadata such as:

- source file ID
- source owner
- project or client association
- source permissions snapshot
- sensitivity label

Example:

Meeting Transcript from Sales Team Drive

**Situation**

1. A sales meeting occurs with Client example_project.
2. The transcript is saved automatically in Google Drive in the personal drive of a sales rep.

Example Drive file:

    Drive owner: maria@company.com
    File name: example_project_Q2_strategy_meeting_transcript.docx
    Drive File ID: 1A9sd23sdf9sdfsd

The ETL pipeline retrieves the document and stores it in GCS so the AI Agent can analyze it.

**Step 1 — File Stored in GCS**

The file might be stored like this:

    gs://enterprise-transcripts/u_maria/proj_example_project/example_project_Q2_strategy_meeting_transcript.docx

**Step 2 — Metadata Stored with the File**

Along with the file, the ETL stores metadata like this:

    {
        "source_system": "google_drive",
        "source_file_id": "1A9sd23sdf9sdfsd",
        "source_owner": "maria@company.com",
        "project_id": "example_project",
        "client_name": "example_project",
        "source_permissions_snapshot": [
            "maria@company.com",
            "sales-manager@company.com"
        ],
        "sensitivity_label": "confidential",
        "contains_pii": true,
        "ingestion_timestamp": "2026-03-10T15:22:11Z"
    }

When documents are synchronized from Google Drive to GCS, the ingestion pipeline must store metadata describing the document’s origin, ownership, and access context. This metadata enables traceability, security filtering, and IAM-aligned retrieval so that Gemini Enterprise Agents only access documents that the invoking user is authorized to view.

### 6.2 Google Calendar
Calendar data should be limited to minimum necessary fields. Examples:

- meeting title
- date and time
- organizer
- participants
- meeting ID or join metadata where needed

Calendar access should also respect user-level authorization and should not become a side channel for exposing private meeting details.

### 6.3 GCS
GCS will be the primary secure storage layer for unstructured synchronized content.

GCS also will be use when share a file with all people in the company will be required, creating a centralized storage with public "open" access to everyone

Recommended path format:
 
    transcript_outputs/<user_id>/<project_id>/<original_document_name>
 
Example:
 
    transcript_outputs/u_2948/proj_example_project_q2/meeting_transcript_2026_03_05.txt
 
This supports policy alignment for ownership and project scoping.

### 6.4 BigQuery
BigQuery should store structured, indexed, or extracted metadata rather than becoming a replacement for the protected raw transcript repository.

BigQuery could also be used to storage logging and security metrics, and also used to createrd cetralized datasets for information that everyone in the company can access it.

BigQuery should use:

- CMEK
- dataset-level IAM
- row-level security and policy tags where applicable
- minimal exposure of raw sensitive text unless truly required

## 7. Security Threat Model

### Threat 1. Unauthorized document retrieval by the AI Agent

**Risk**

The agent retrieves documents outside the invoking user’s authorization scope.

**Mitigations**

- User-context propagation on every retrieval request
- IAM-enforced access checks before retrieval
- Metadata-based filtering using source ownership and project scope
- Deny-by-default retrieval policy
- Periodic access review and validation tests

### Threat 2. PII leakage through logs, traces, or telemetry

**Risk**

Operational logs inadvertently store raw transcript text, names, or confidential project details.

**Mitigations**

- Do not log raw prompts or retrieved documents by default
- Store only metadata and identifiers in logs
- Apply redaction controls to logging middleware
- Use DLP inspection for sensitive logging pipelines where needed
- Restrict log viewer permissions

### Threat 3. Data exfiltration from storage or service perimeter
**Risk**
Sensitive synchronized content is copied outside the trusted environment.

**Mitigations**

- VPC Service Controls around sensitive projects and services
- Restricted service accounts
- Private networking where possible
- CMEK encryption
- Egress controls and monitoring
- Separation of environments

### Threat 4. Over-privileged ETL connector  / MCP-Server OAuth

**Risk**

The ETL service gains access to more Drive or storage content than necessary.

**Mitigations**

- Least-privilege IAM
- Source-specific scopes only
- Separate service identities by connector or environment
- Prefer delegated access aligned to source permissions
- Access reviews and audit monitoring

### Threat 5. Key compromise or improper key administration

**Risk**

An attacker or over-privileged admin obtains encryption key access.

**Mitigations**

- Cloud KMS with restricted admin roles
- Key rotation
- Key access auditing
- Separation of key admin and data admin duties
- Alerting on unusual KMS activity

### Threat 6. Sensitive context leakage through model interaction patterns

**Risk**
Unmasked content exposed to an LLM may appear in outputs beyond intended scope.

**Mitigations**

- Retrieval restricted to authorized content only
- Prompt construction should minimize unnecessary context
- Output-layer policy checks where appropriate
- Human review for highly sensitive workflows
- Strong data classification and environment scoping

## 8. Implementation Guidelines for Engineering
### 8.1 Storage Structure
Use a consistent object path pattern:
 
    transcript_outputs/<user_id>/<project_id>/<original_document_name>
 
Required metadata fields should include at least:

- user_id
- project_id
- source_system
- source_document_id
- source_owner
- classification
- contains_pii
- last_synced_at

### 8.2 Access Model
- Retrieval services must require invoking user identity
- Service accounts or OAuth tokens should not bypass user authorization checks except for approved administrative workflows

### 8.3 Logging Rules
Never log:

- raw transcript text
- contract bodies
- prompt bodies containing sensitive content
- participant lists unless required and explicitly controlled

Prefer logging:

- request ID
- user ID
- document ID
- access outcome
- connector name
- sensitivity classification

### 8.4 Source Ingestion Priority
- Shared Drive ingestion is preferred where enterprise control is possible
- Personal Drive ingestion is allowed only with explicit permission model and documented ownership mapping
- Calendar ingestion should be minimum-necessary

## 9. Consequences
### 9.1 Positive
- Preserves high-value AI context
- Aligns with least-privilege principles
- Supports multiple data sources consistently
- Reduces damage caused by irreversible redaction
- Easier to reason about business correctness

### 9.2 Negative
- Requires strong identity propagation design
- Requires disciplined logging controls
- More sensitive operational posture because original content remains accessible to approved services

## 10. Final Recommendation
Adopt a **preserve-and-protect strategy**:

- Preserve original content for AI reasoning
- Protect it with IAM, user-context authorization, CMEK, secure transport, VPC Service Controls, and sanitized logging
- Use DLP for inspection and classification, not default irreversible redaction
- Use tokenization only for selective structured fields
- Keep the ETL as a secure synchronization layer

This approach best satisfies the project requirement of enabling Gemini Enterprise AI Agents to operate on accurate, unmasked enterprise data without sacrificing security and compliance.