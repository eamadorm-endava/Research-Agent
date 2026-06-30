---
name: kb-file-ingestion
description: Orchestrates privacy-preserving ingestion of user-uploaded PDF files into the Enterprise Knowledge Base using a metadata-first workflow. Use when a user asks to save, add, publish, register, upload, or ingest documents into the EKB/KB, or asks which EKB project IDs are available for file metadata. The skill prioritizes user-provided project, domain, trust-level, and PII metadata, must not read uploaded file contents unless the user explicitly requests content-based inspection, and can query the KB BigQuery dataset to list or validate available project IDs.
---

## Mandatory execution mode

Trigger this skill when a user asks to:
- "Save / add / ingest / publish / upload / register this file to the knowledge base / EKB / KB"
- "What projects can I use for the metadata?" or "Which project IDs are available in the KB?"
or similar requests.

## Core Privacy Rule

- Do **not** read, parse, OCR, preview, or extract text from uploaded files by default.
- The user-uploaded file is automatically injected into the conversation context by the UI plugin, meaning you already have access to its contents natively if needed. Do NOT inspect the file contents unless the user explicitly asks you to do so to infer metadata.
- Leave any field that cannot be inferred blank (`—`) and ask the user — do not read file contents to fill gaps.

## Required Metadata

Every ingested file must have:
- **Project**: an `ekb_project_name` confirmed by the user after project validation.
- **Domain**: one of `IT`, `Finance`, `HR`, `Sales`, `Executives`, `Legal`, `Operations`.
- **Trust-level**: one of `Published`, `WIP`, `Archived`.
- **PII**: `Yes` or `No`.

## Metadata Inference

Before asking the user, infer metadata from the current message, conversation history, and filenames using these mappings:

**Domain:**

| Keywords | Domain |
|---|---|
| technical, engineering, architecture, software, cloud, data, integration, API | `IT` |
| budget, invoice, forecast, financial, accounting, revenue, cost | `Finance` |
| people, hiring, performance, benefits, employee, onboarding | `HR` |
| proposal, pipeline, account plan, commercial, pricing, lead, opportunity | `Sales` |
| strategy, leadership, board, executive, roadmap, operating model | `Executives` |
| contract, compliance, legal, policy, audit, risk, privacy terms | `Legal` |
| process, procedure, operations, runbook, support, delivery, governance | `Operations` |

**Trust-level:**

| Keywords | Trust-level |
|---|---|
| final, approved, published, production, official, signed-off | `Published` |
| draft, WIP, work in progress, preliminary, review, v0.x, unapproved | `WIP` |
| archived, deprecated, superseded, obsolete, historical, retired | `Archived` |

Do not infer `PII = No` from silence. Only set it if the user stated it or the filename clearly signals anonymized/redacted content.

## Gotchas

- **Agent landing zone**: always `gs://<project_id>-ai-agent-landing-zone/`.
- **KB Landing Zone**: use `<project_id>-kb-landing-zone` as `destination_bucket`. Note: The orchestrator should provide `<project_id>`.
- **BigQuery project**: query `knowledge_base.documents_metadata` directly. Do not use a project prefix.
- **Perceived-speed rule**: once the user confirms the metadata table, use the unified `submit_kb_ingestion_batch` tool. Do not orchestrate separate `get_artifact_uri`, `upload_object`, and `trigger_ekb_pipeline` calls unless the unified tool fails and a retry requires a lower-level fallback.
- **Job IDs**: always return the `job_id` from **each entry** in `file_responses` from `submit_kb_ingestion_batch`. If a file response has no `job_id`, show its `execution_message` instead.
- **Status checks**: do not call `check_ingestion_status` immediately after submission. Return the initial job IDs/statuses as soon as `submit_kb_ingestion_batch` completes. Only check status if the user explicitly asks for a status update.

---

## Workflow

### Step 1 — Validate File Types

Validate if each file is a PDF simply by checking its filename extension in the provided context (do not call `get_artifact_uri` here). For each file:
- **Not a PDF** → tell the user: *"The EKB only accepts PDF documents. Please convert `<filename>` to PDF and upload it again."* Exclude it from the batch.
- **No valid PDFs remain** → stop and ask the user to upload PDF documents.

Proceed only with confirmed PDF files.

---

### Step 2 — Infer Metadata

Extract all metadata fields for every valid PDF. Priority order — use the first source that provides a value:

1. **User's message** (explicit, highest priority): e.g., *"upload this to project Alpha, domain IT, WIP, no PII"*
2. **Conversation history**: values confirmed or mentioned in prior turns
3. **Filename**: keywords that map to domain or trust-level (see mappings above)

Do not read file contents. Leave any field that cannot be obtained as `—`.

**As soon as the project name is known** — whether the user stated it directly or it was inferred — fire the **Pre-flight Verification Query** (see appendix) *immediately in parallel* with assembling the metadata table. Do not wait for user confirmation first. Build the token pattern and strip the extensions from every filename before querying (see appendix).

---

### Step 3 — Present Metadata Table and Confirm

Always assemble and present the metadata table, even if the user already provided every required metadata field in the same message. The confirmation step is mandatory for every ingestion attempt. Do not proceed to upload or submission until the user explicitly confirms the table.

Assemble the metadata table and — if the project validation result is already available — present both in a single message:

> | File | Project | Domain | Trust-level | PII |
> |:---:|:---:|:---:|:---:|:---:|
> | `<file1.pdf>` | `<value>` | `<value>` | `<value>` | `<Yes/No>` |
>
> **Domain**: `IT` · `Finance` · `HR` · `Sales` · `Executives` · `Legal` · `Operations`
> **Trust-level**: `Published` (official) · `WIP` (draft) · `Archived` (historical)
>
> *(List any blank `—` fields here and ask the user to fill them)*

Handle the pre-flight verification result:

- **Matches found** → append to the same message:
  > *"I also found existing project(s) with a similar name in the EKB: `<list>`. Would you like to use one of these, or proceed with `<user's value>` as a new project?"*
  - User picks an existing project → check the query results for duplicates in that project.
    - **Duplicate found** → ask: *"A file named `<filename>` already exists in project `<ekb_project_name>` (Domain: `<domain>`, Trust-level: `<trust_level>`). Would you like to Replace it (inheriting its metadata) or Upload as new (provide a new filename)?"*
      - User chooses **Replace** → override this file's `domain` and `trust_level` with the values from the existing BigQuery record. Do not use inferred or user-typed values for those fields.
      - User chooses **Upload as new** → update the filename to what the user provides.
    - **No duplicate** → keep the selected project in the table and wait for explicit confirmation before Step 4.
  - User creates a new project → keep the user's project value in the table and wait for explicit confirmation before Step 4.
- **No matches found** → show the table normally; project proceeds as new after explicit confirmation.
- **Project was blank** (`—`) → ask the user to fill it. Once provided, immediately run the Pre-flight Verification Query and present the result before proceeding.

**Do not proceed to Step 4 until all required fields are filled, any duplicates resolved, and the user explicitly confirms the metadata table. This applies even when all metadata was provided up front.**

---

### Step 4 — Submit Confirmed Batch

After the user confirms the metadata table, call `submit_kb_ingestion_batch` exactly once for the confirmed batch. This unified tool resolves session artifact URIs, copies files to the KB landing-zone bucket with metadata, triggers the EKB pipeline, and returns initial job IDs.

Call arguments:
- `files`: one object per confirmed PDF.
  - `filename`: confirmed filename.
  - `project`: confirmed `ekb_project_name`.
  - `domain`: confirmed domain.
  - `trust_level`: confirmed trust-level. Use the underscore key expected by the tool, not `trust-level`.
  - `pii_status`: confirmed `Yes` or `No`.
- `destination_bucket`: omit unless the user or environment explicitly requires a non-default KB landing-zone bucket. The tool defaults to `<project_id>-kb-landing-zone`.

Do **not** call `get_artifact_uri`, `upload_object`, or `trigger_ekb_pipeline` directly during the normal path. The unified tool performs those operations internally to reduce agent/tool round trips.

Do **not** call `check_ingestion_status` after `submit_kb_ingestion_batch` in the same turn. Treat the returned initial job IDs as the completion of the user-facing submission step; processing continues asynchronously.

**Final Summary** — iterate `file_responses` to build the table:
```markdown
### Ingestion Started
| File | Project | Job ID | Status |
|:---:|:---:|:---:|:---:|
| <file1.pdf> | <project> | <file_responses[0].job_id> | <file_responses[0].job_status> |
```

If a file has `execution_status = "error"`, show its `execution_message` in the status column and do not claim that ingestion started for that file.

---

### Retry Protocol

If the failure happened after the user already confirmed metadata, skip Steps 1–3 and call `submit_kb_ingestion_batch` again using the previously confirmed filenames, EKB project names, and metadata. If the retry also fails, report the error and ask how to proceed.

---

### Project Discovery (no files uploaded)

When the user asks which projects are available without uploading files:
1. Run the **Project Discovery Query** (see appendix).
2. Return a table of `ekb_project_name`, document count, and domains.
3. If no rows are returned, say no projects were found. If the query fails, report the error.

---

## Queries

### Project Discovery Query
```sql
SELECT DISTINCT project_id
FROM `knowledge_base.documents_metadata`
WHERE project_id IS NOT NULL
  AND TRIM(project_id) != ''
ORDER BY project_id
LIMIT 100
```

### Pre-flight Verification Query

Construct `<token_pattern>` before running: tokenize the confirmed project name on spaces, hyphens, and underscores; join with `%` and wrap with leading/trailing `%`.
Examples: `"Project Alpha"` → `%project%alpha%` · `"My-Cool Project"` → `%my%cool%project%`.
Strip the extension from every uploaded filename before building the `UNNEST` list (e.g., `report.pdf` → `report`).

```sql
WITH uploaded_files AS (
  SELECT filename_base
  FROM UNNEST(['<base1>', '<base2>', ...]) AS filename_base
),
matched_projects AS (
  SELECT DISTINCT project_id
  FROM `knowledge_base.documents_metadata`
  WHERE LOWER(project_id) LIKE LOWER('<token_pattern>')
  LIMIT 5
)
SELECT
  p.project_id AS matched_project,
  ARRAY_AGG(
    STRUCT(u.filename_base AS user_filename, m.filename, m.domain, m.trust_level, m.classification_tier)
    IGNORE NULLS
  ) AS duplicate_files
FROM matched_projects p
CROSS JOIN uploaded_files u
LEFT JOIN `knowledge_base.documents_metadata` m
  ON m.project_id = p.project_id
  AND LOWER(m.filename) LIKE LOWER(CONCAT('%', u.filename_base, '%'))
  AND m.latest = TRUE
GROUP BY p.project_id
```
