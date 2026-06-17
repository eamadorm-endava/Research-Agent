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
- **Job IDs**: always return the `job_id` from the pipeline response to the user.

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
    - **No duplicate** → proceed to **Step 4**.
  - User creates a new project → skip Step 4, proceed to **Step 4**.
- **No matches found** → show the table normally; project proceeds as new, skip Step 4.
- **Project was blank** (`—`) → ask the user to fill it. Once provided, immediately run the Pre-flight Verification Query and present the result before proceeding.

**Do not proceed to Step 4 until all required fields are filled, any duplicates resolved, and the user confirms.**

---

### Step 4 — Upload and Trigger

For all files **simultaneously**:

**4a — Upload and Stamp**
Call `get_artifact_uri` to get the GCS URI for each file.
Then call `upload_object` for every file at the same time:
- `source_gcs_uri`: URI from `get_artifact_uri`.
- `destination_bucket`: `<project_id>-kb-landing-zone`
- `filename`: confirmed filename.
- `path_inside_bucket`: confirmed `ekb_project_name`.
- `metadata`: A JSON object containing `project`, `domain`, `trust-level`, and `pii_status`.

**4b — Trigger Pipeline** *(after all uploads complete)*
Call `trigger_ekb_pipeline(gcs_uris=['<uri1>', '<uri2>', ...])` once with all URIs returned by the upload calls. The tool triggers all pipelines in parallel internally and returns one result per file.

**Final Summary:**
```markdown
### Ingestion Started
| File | Project | Job ID | Status |
|:---:|:---:|:---:|:---:|
| <file1.pdf> | <ekb_project_name> | <job_id> | <status> |
```

---

### Retry Protocol

Skip Steps 1–3. Execute Steps 4a → 4b using the previously confirmed URIs, filenames, EKB project names, and metadata. If the retry also fails, report the error and ask how to proceed.

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
