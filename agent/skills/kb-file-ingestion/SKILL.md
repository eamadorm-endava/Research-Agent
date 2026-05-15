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
- Do **not** call `import_gcs_to_artifact` or `load_artifacts` unless the user explicitly asks to infer metadata from file contents.
- Infer metadata from the user's message, conversation history, and filenames only.
- Leave any field that cannot be inferred blank (`—`) and ask the user — do not read file contents to fill gaps.

## Required Metadata

Every ingested file must have:
- **Project**: a `project_id` confirmed by the user after project validation.
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

- **Agent landing zone**: always `gs://ai_agent_landing_zone/`.
- **KB Landing Zone**: use `ag-core-dev-fdx7-kb-landing-zone` as `destination_bucket` — this triggers the Service Account authentication switch.
- **BigQuery project**: use `ag-core-dev-fdx7` as the tool `project_id`; query `ag-core-dev-fdx7.knowledge_base.documents_metadata`.
- **Job IDs**: always return the `job_id` from the pipeline response to the user.
- **Parallelism**: when ingesting more than one file, all upload, stamp, and pipeline calls must be launched simultaneously — never one-by-one.

---

## Workflow

### Step 1 — Validate File Types

Call `get_artifact_uri` for every uploaded file simultaneously. For each file:
- **Not a PDF** → tell the user: *"The EKB only accepts PDF documents. Please convert `<filename>` to PDF and upload it again."* Exclude it from the batch.
- **No valid PDFs remain** → stop and ask the user to upload PDF documents.

Proceed only with confirmed PDF files.

---

### Step 2 — Infer and Collect Metadata

For each valid PDF, infer metadata from the user's message, conversation history, and filename using the mappings above. Do not read file contents.

- If the user provided batch-level metadata (e.g., *"all files are project X, domain IT, published, no PII"*), apply it to all files.
- If the user provided per-file metadata, apply it per file and use batch values as defaults for the rest.
- Leave any field that cannot be inferred as `—`.

---

### Step 3 — Project Validation and Dedup Check

#### 3a — Project Validation

For each unique project value provided or inferred, run the **Project Validation Query** (see appendix).

- **One or more matches found** → inform the user:
  > *"I found project(s) with a similar name in the EKB: `<list>`. Would you like to use one of these, or proceed with `<user's value>` as a new project?"*
  - User selects an existing project → use that `project_id`, then run **3b**.
  - User creates a new project → use the user-provided value as the `project_id`, skip 3b.
- **No match found** → proceed with the user-provided value as the `project_id`, skip 3b.

#### 3b — Dedup Check *(only when the user selected an existing project)*

Run the **Dedup Query** (see appendix) once for all files simultaneously. Strip the extension from every filename before building the query (e.g., `report.pdf` → `report`).

The query returns one row per uploaded file with an array of matching EKB records. Process the results:

- **`ekb_matches` is non-empty** → inform the user for each affected file:
  > *"A file named `<filename>` already exists in project `<project_id>` (Domain: `<domain>`, Trust-level: `<trust_level>`, Classification: `<classification_tier>`). Would you like to:*
  > - **Replace** it — the existing domain, trust-level, and classification tier will be used as the metadata for this file.
  > - **Upload as new** — please provide a different filename."*
  - User chooses **Replace** → override this file's `domain`, `trust_level`, and `classification_tier` with the values from the existing BigQuery record. Do not use inferred or user-typed values for those fields.
  - User chooses **Upload as new** → update the filename to what the user provides.
- **`ekb_matches` is empty** → no duplicate, proceed normally.

---

### Step 4 — Confirm Metadata, Upload, and Trigger

Present the complete metadata table to the user for confirmation:

> | File | Project | Domain | Trust-level | PII |
> |:---:|:---:|:---:|:---:|:---:|
> | `<file1.pdf>` | `<value>` | `<value>` | `<value>` | `<Yes/No>` |
>
> **Domain**: `IT` · `Finance` · `HR` · `Sales` · `Executives` · `Legal` · `Operations`
> **Trust-level**: `Published` (official) · `WIP` (draft) · `Archived` (historical)
>
> *(List any blank `—` fields here and ask the user to fill them before confirming)*
>
> Please confirm the metadata to proceed with ingestion.

**Do not proceed until the user explicitly confirms and all required fields are filled.**

Once confirmed, for all files **simultaneously**:

**4a — Upload**
Call `upload_object` for every file at the same time:
- `source_gcs_uri`: URI from Step 1.
- `destination_bucket`: `ag-core-dev-fdx7-kb-landing-zone`
- `filename`: confirmed filename.
- `path_inside_bucket`: confirmed `project_id`.

**4b — Stamp Metadata** *(after all uploads complete)*
Call `update_object_metadata` for every file at the same time:
```json
{
  "project": "<project_id>",
  "domain": "<domain>",
  "trust-level": "<trust_level>",
  "pii_status": "<Yes or No>"
}
```

**4c — Trigger Pipeline** *(after all stamps complete)*
Call `trigger_ekb_pipeline(gcs_uri='<uri_returned_by_upload_object>')` for every file at the same time.

**Final Summary:**
```markdown
### Ingestion Started
| File | Project | Job ID | Status |
|:---:|:---:|:---:|:---:|
| <file1.pdf> | <project_id> | <job_id> | <status> |
```

---

### Retry Protocol

Skip Steps 1–3. Execute Steps 4a → 4b → 4c using the previously confirmed URIs, filenames, project IDs, and metadata. If the retry also fails, report the error and ask how to proceed.

---

### Project Discovery (no files uploaded)

When the user asks which projects are available without uploading files:
1. Run the **Project Discovery Query** (see appendix).
2. Return a table of `project_id`, document count, and domains.
3. If no rows are returned, say no projects were found. If the query fails, report the error.

---

## Queries

### Project Discovery Query
```sql
SELECT
  project_id,
  COUNTIF(latest = TRUE) AS latest_document_count,
  ARRAY_AGG(DISTINCT domain IGNORE NULLS ORDER BY domain LIMIT 10) AS domains
FROM `ag-core-dev-fdx7.knowledge_base.documents_metadata`
WHERE project_id IS NOT NULL
  AND TRIM(project_id) != ''
GROUP BY project_id
ORDER BY project_id
LIMIT 500
```

### Project Validation Query
```sql
SELECT DISTINCT project_id
FROM `ag-core-dev-fdx7.knowledge_base.documents_metadata`
WHERE LOWER(project_id) LIKE LOWER('%<user_supplied_project_id>%')
LIMIT 5
```

### Dedup Query
Strip the extension from every uploaded filename before building the `UNNEST` list (e.g., `report.pdf` → `report`). One query covers all files at once and returns each user filename alongside an array of matching EKB records.

```sql
WITH uploaded_files AS (
  SELECT filename_base
  FROM UNNEST(['<base1>', '<base2>', ...]) AS filename_base
)
SELECT
  u.filename_base AS user_filename,
  ARRAY_AGG(
    STRUCT(m.filename, m.domain, m.trust_level, m.classification_tier)
    IGNORE NULLS
  ) AS ekb_matches
FROM uploaded_files u
LEFT JOIN `ag-core-dev-fdx7.knowledge_base.documents_metadata` m
  ON LOWER(m.filename) LIKE LOWER(CONCAT('%', u.filename_base, '%'))
  AND m.project_id = '<confirmed_project_id>'
  AND m.latest = TRUE
GROUP BY u.filename_base
```
