---
name: kb-file-ingestion
description: Orchestrates privacy-preserving ingestion of user-uploaded PDF files into the Enterprise Knowledge Base using a metadata-first workflow. Use when a user asks to save, add, publish, register, upload, or ingest documents into the EKB/KB, or asks which EKB project IDs are available for file metadata. The skill prioritizes user-provided project, domain, trust-level, and PII metadata, must not read uploaded file contents unless the user explicitly requests content-based inspection, and can query the KB BigQuery dataset to list or validate available project IDs.
---

## Mandatory execution mode

Trigger this skill when a user asks to:
- "Save this file to the knowledge base"
- "Add this document to the general KB"
- "Make this file available for the whole company"
- "Ingest this into the EKB"
- "Publish the uploaded file to the EKB"
- "Upload the file to the database"
- "Register this document in EKB"
- "Upload it to KB"
- "What projects can I use for the metadata?"
- "Which project IDs are available in the KB?"
- "Show me the EKB projects I can ingest into"
or similar requests.

## Core Privacy and Optimization Rule

Use a **privacy-preserving metadata-first ingestion flow**. The goal is to minimize processing time while avoiding unnecessary access to uploaded file contents.

- Do **not** read, parse, OCR, preview, summarize, or extract text from uploaded PDFs by default.
- Do **not** call `import_gcs_to_artifact` or `load_artifacts` for uploaded PDFs unless the user explicitly asks the agent to read or infer metadata from file contents.
- Treat requests like "ingest this", "upload these", "add to KB", or "fill metadata" as **not consent** to inspect file contents.
- First use the user's current message, prior conversation context, uploaded filenames, and lightweight URI/file metadata to infer the four required metadata fields.
- Prefer asking the user to confirm or fill missing metadata over reading file contents.
- If the user asks which projects are available for metadata, query the KB BigQuery dataset and answer from that query; do not inspect uploaded files.
- Never start upload/stamping/pipeline steps until the user explicitly confirms the final metadata plan.

## Required Metadata

Every ingested file must have:
- **Project**: confirmed EKB `project_id` after validation against the KB dataset or semantic project validation.
- **Domain**: one of `IT`, `Finance`, `HR`, `Sales`, `Executives`, `Legal`, `Operations`.
- **Trust-level**: one of `Published`, `WIP`, `Archived`.
- **PII**: `Yes` or `No`.

## Project ID Discovery Requests

When the user asks which projects can be used for metadata, which project IDs are available, or asks for help choosing a project before ingestion:

1. Do **not** read any uploaded files.
2. Query BigQuery using `execute_query` with `project_id="ag-core-ops-auj0"`.
3. Use this read-only SQL:
   ```sql
   SELECT
     project_id,
     COUNTIF(latest = TRUE) AS latest_document_count,
     ARRAY_AGG(DISTINCT domain IGNORE NULLS ORDER BY domain LIMIT 10) AS domains
   FROM `ag-core-ops-auj0.knowledge_base.documents_metadata`
   WHERE project_id IS NOT NULL
     AND TRIM(project_id) != ''
   GROUP BY project_id
   ORDER BY project_id
   LIMIT 500
   ```
4. Return the available `project_id` values in a concise table. Include document counts and domains when returned by the query.
5. If the query returns no rows, say that no project IDs were found in the KB metadata table.
6. If the query fails, report the BigQuery error and do not guess project IDs.
7. If files are already uploaded, ask the user to choose one of the returned project IDs and provide or confirm the remaining metadata before continuing ingestion.

Use the query results as a metadata aid only. Do not auto-select a project ID for a file unless the user clearly asked for a specific project or there is a high-confidence semantic match that the user later confirms.

## Metadata Source Precedence

When multiple sources provide a value for the same field, apply this precedence:

1. Explicit per-file user input.
2. Explicit batch-level user input, such as "all files are for project X" or "same metadata for all PDFs".
3. Previously confirmed values in the same conversation.
4. BigQuery project ID discovery or validation results, when matching a user-provided project name or ID.
5. Lightweight filename/URI hints.
6. User-authorized file-content inspection results, only when the user explicitly requested content-based inference.
7. Blank (`—`) and ask the user.

**Duplicate replace exception**: If the user chooses **Replace** for a duplicate file, override that file's `domain` and `trust-level` with the values fetched from the existing BigQuery metadata record. This override beats all inferred or user-typed values for those two fields.

## Progress Tracker

Maintain this state throughout the interaction:
- [ ] Optional project lookup: If the user asks for available projects, query BigQuery and show project IDs without reading files
- [ ] Step 1a: Get URIs for all uploads → validate every file is a PDF
- [ ] Step 1b: Parse user-provided metadata and lightweight file hints → build metadata candidates without reading PDFs
- [ ] Step 1c: Privacy gate → read file contents only if the user explicitly requested content-based inspection for specific files or fields
- [ ] Step 2 (background, all in parallel): Project validation + deduplication check for every resolvable file simultaneously
- [ ] Step 2 (user-facing): Present ONE combined message — pre-filled metadata table + any ambiguity/duplicate/missing-field questions + confirmation ask
- [ ] Step 2 (await): Wait for explicit user approval covering metadata AND all open questions
- [ ] Step 3a: Upload files to KB landing zone (all files in parallel)
- [ ] Step 3b: Stamp metadata on uploaded files (all files in parallel, after 3a completes)
- [ ] Step 3c: Verify every file — object exists AND metadata is complete (all files in parallel)
- [ ] Step 4: Trigger EKB pipeline for verified files only + consolidated final summary

**On retry**: Steps 1 and 2 are already complete — jump directly to Step 3a using the previously confirmed file URIs, filenames, project IDs, and metadata.

## Gotchas

- **GCS URIs**: The agent landing zone is always `gs://ag-core-ops-auj0-ai-agent-landing-zone/`.
- **KB Landing Zone**: The KB ingestion bucket is **`gs://ag-core-ops-auj0-kb-landing-zone/`**. You MUST use this exact name for the `destination_bucket` to trigger the Service Account authentication switch.
- **BigQuery project for KB metadata queries**: Use `ag-core-ops-auj0` as the BigQuery tool `project_id` and query `ag-core-ops-auj0.knowledge_base.documents_metadata`.
- **Project IDs**: In BigQuery, `project_id` is case-sensitive in some operations but should be checked case-insensitively for duplicates.
- **Job IDs**: Always return the `job_id` from the pipeline response to the user as a confirmation.
- **Parallelism**: Steps 2 background checks, 3a, 3b, 3c, and 4 each launch ALL eligible tool calls at the same time. Never loop one-by-one.
- **No file-content reads without consent**: Never read PDF content to pre-fill metadata unless the user explicitly requests it. Missing metadata should remain blank and be asked for.

## Mandatory Workflow

### Step 0: Answer Available-Project Questions Before Ingestion

If the user asks which projects are available or which project ID to use, run the **Project ID Discovery Requests** protocol before any ingestion-specific metadata inference. This applies even if the user uploaded files in the same message.

After showing the available project IDs:
- If the user has not chosen a project, ask them to choose one and provide or confirm the remaining required metadata.
- If the user already provided enough metadata, continue to Step 1 without reading file contents.

### Step 1: Identify, Validate, and Infer Metadata Without File Reads

#### 1a — Identify & Validate

1. Call `get_artifact_uri` for every file the user uploaded.
2. For each file:
   - If not a PDF (e.g. `.docx`, `.txt`): inform the user "Endava's Knowledge Base only accepts PDF documents. Please convert `<filename>` to PDF and upload it again." Exclude it from the batch.
   - If no PDFs are found at all: ask "Please upload the PDF document(s) you'd like to add to the knowledge base."
3. Proceed only with the confirmed PDF files.

#### 1b — Parse User Metadata and Lightweight Hints *(no PDF content reads)*

Before reading any file content, extract metadata candidates from the current user message and conversation history.

Recognize batch-level statements, for example:
- "All files are for project Phoenix, domain IT, published, no PII."
- "Same metadata for all PDFs: project = ACME migration, trust = WIP."
- "Ingest these under project `abc-123`; they are Finance docs and contain PII."

Recognize per-file statements, for example:
- "`architecture.pdf` is IT / Published / No PII; `budget.pdf` is Finance / WIP / Yes PII."
- Markdown tables with columns like file, project, domain, trust, pii.
- Inline mappings such as `file1.pdf -> project X, Legal, Archived, no PII`.

Normalize values using these mappings:

**Domain**
- Technical, engineering, architecture, software, cloud, data, integration, API → `IT`
- Budget, invoice, forecast, financial, accounting, revenue, cost → `Finance`
- People, hiring, performance, benefits, employee, onboarding → `HR`
- Proposal, pipeline, account plan, commercial, pricing, lead, opportunity → `Sales`
- Strategy, leadership, board, executive, roadmap, operating model → `Executives`
- Contract, compliance, legal, policy, audit, risk, privacy terms → `Legal`
- Process, procedure, operations, runbook, support, delivery, governance → `Operations`

**Trust-level**
- Final, approved, published, production, official, signed-off → `Published`
- Draft, WIP, work in progress, preliminary, review, v0.x, unapproved → `WIP`
- Archived, deprecated, superseded, obsolete, historical, retired → `Archived`

**PII**
- `No`: no PII, anonymized, redacted, sanitized, public-safe, contains no personal data
- `Yes`: contains PII, personal data, employee/customer names, emails, phone numbers, IDs, resumes, CVs, HR data

Use filenames and URIs only for lightweight hints. Examples:
- `draft-architecture.pdf` can hint `WIP` and `IT`.
- `finance-forecast-final.pdf` can hint `Finance` and `Published`.
- `archive-legal-contract.pdf` can hint `Legal` and `Archived`.

Do not infer `PII = No` from silence alone. If the user does not provide PII status and the file name does not clearly indicate redacted/anonymized content, leave PII blank (`—`) and ask the user.

#### 1c — Privacy Gate for Optional File-Content Inspection

File-content inspection is **opt-in only**.

Only read uploaded PDF contents when the user explicitly asks for it using language such as:
- "Read the file and infer the metadata."
- "You may inspect the documents to fill missing metadata."
- "Auto-detect PII/domain/trust level from the contents."
- "Scan the PDFs and tell me the metadata."

When the user has not explicitly requested content-based inspection:
- Do **not** call `import_gcs_to_artifact`.
- Do **not** call `load_artifacts`.
- Leave unresolved fields blank (`—`) and ask the user for the missing metadata in Step 2.

When the user explicitly requests content-based inspection:
- Read only the specific files or fields the user authorized, not the entire batch unless the user clearly authorized the entire batch.
- For every selected PDF, call `import_gcs_to_artifact(gcs_uri=<uri>, mime_type="application/pdf")` then `load_artifacts`.
- Extract only the missing or requested metadata hints needed for that file.
- If a selected file cannot be read, leave unresolved fields blank (`—`) and continue.
- In the Step 2 message, state that user-authorized file-content checks were used.

### Step 2: Background Validation → Single User-Facing Message

#### Background *(run immediately after Step 1 metadata inference, all eligible checks launched in parallel)*

Merge metadata candidates from Step 1b/1c using the precedence rules above.

1. **Project Validation** — for every unique project name or project-like value inferred:
   - If the user provided an exact-looking `project_id`, validate it against BigQuery with a read-only `execute_query` against `ag-core-ops-auj0.knowledge_base.documents_metadata`.
   - If the user provided a project name or description rather than an exact ID, call `ekb_semantic_search(query='<inferred_project_name>')` and resolve only high-confidence matches.
   - Direct `project_id` supplied by the user and validated → use that `project_id`.
   - High-confidence single semantic match → resolve to that `project_id`.
   - Multiple plausible matches → collect the candidates; surface them as an inline ⚠️ question in the user-facing message.
   - No match → leave the project cell blank; flag it as missing input in the message.

   Exact project ID validation query:
   ```sql
   SELECT DISTINCT project_id
   FROM `ag-core-ops-auj0.knowledge_base.documents_metadata`
   WHERE LOWER(project_id) = LOWER('<user_supplied_project_id>')
   LIMIT 5
   ```

2. **Deduplication Check** — for each file whose project resolved to a confirmed `project_id`, run:
   ```sql
   SELECT filename, domain, trust_level
   FROM `ag-core-ops-auj0.knowledge_base.documents_metadata`
   WHERE project_id = '<confirmed_project_id>'
     AND lower(filename) = lower('<uploaded_filename>')
     AND latest = TRUE
   LIMIT 1
   ```
   - Duplicate found → record the existing `domain` and `trust_level`; surface a replace-or-rename question in the user-facing message.
   - No duplicate → no extra question for this file.
   - If the project was ambiguous or unresolved, skip the dedup check for that file — it will run after the user confirms the project.

#### User-Facing Message *(one message only, sent after all background checks complete)*

Send a single message with this structure:

> "Based on your instructions and the available file metadata, I have pre-filled the metadata to be used without reading the uploaded file contents. Please let me know if it's correct or if you want to make changes, and answer any questions below before I proceed:
>
> | File | Project | Domain | Trust-level | PII |
> |:---:|:---:|:---:|:---:|:---:|
> | `<file1.pdf>` | `<value>` | `<value>` | `<value>` | `<Yes/No>` |
> | `<file2.pdf>` | — | `<value>` | `<value>` | `<Yes/No>` |
>
> **Domain options**:
>   - `IT`
>   - `Finance`
>   - `HR`
>   - `Sales`
>   - `Executives`
>   - `Legal`
>   - `Operations`
>
> **Trust-level options**:
>   - `Published` — verified & ready for company-wide use
>   - `WIP` — draft still being refined
>   - `Archived` — historical reference, no longer active
>
> *(question blocks appear here only when there are open issues — see rules below, a bullet point per question)*
>
> Please confirm the metadata and answer any question(s) above to proceed."

If user-authorized file-content checks were actually performed, use this first sentence instead:

> "Based on your instructions, available file metadata, and user-authorized file-content checks, I have pre-filled the metadata to be used."

**Cell formatting rules:**
- Write only the metadata value in every cell, regardless of how it was obtained.
- If a value cannot be inferred from any allowed source, use `—` with no additional text.
- The Project cell must display the resolved `project_id` when available, not merely the raw project name.

**⚠️ Issue blocks** (append below the table, one block per open issue; omit entirely if no issues exist):

For missing required metadata:
> ⚠️ **Metadata missing for `<filename>`**: Please provide `<Project/Domain/Trust-level/PII>` for this file. I will not read the file to infer this unless you explicitly ask me to inspect its contents.

For an ambiguous project match:
> ⚠️ **Project unclear for `<filename>`**: I found multiple possible matches in the EKB. Is it one of these?
> - `<Project Name A>` (ID: `<id_a>`)
> - `<Project Name B>` (ID: `<id_b>`)

For a duplicate filename:
> ⚠️ **Duplicate detected for `<filename>`**: A version already exists in `<project_id>` (Domain: `<existing_domain>`, Trust-level: `<existing_trust_level>`). Should I:
> - **Replace** the existing file (its domain and trust-level will be preserved from the existing record)
> - **Rename** `<filename>` — please provide the new filename

**MANDATORY — Replace rule**: If the user chooses Replace for any file, override that file's `domain` and `trust-level` in the ingestion plan with the values fetched from the existing BigQuery record. Do NOT use inferred or user-typed values for those two fields.

#### Awaiting User Response

Do NOT start Step 3a until all conditions are met:
1. The user has explicitly confirmed the metadata table or provided corrections.
2. Every ⚠️ duplicate question has been answered (Replace, or Rename with a new filename).
3. Every blank (`—`) required metadata cell has been resolved.
4. Every project value has been resolved to a confirmed `project_id`.

If the user corrects a project name that was previously unresolved or wrong, re-run project validation and, if it resolves, run the dedup check for that file before proceeding.

If the user provides missing metadata in response to the table, update the affected rows, re-display the corrected table, and ask for confirmation again before continuing.

If the user asks the agent to auto-detect missing fields from the documents after seeing the table, run user-authorized file-content inspection only for the files and fields the user asked to auto-detect, then re-display the corrected table.

### Step 3a: Upload Files *(all files launched in parallel simultaneously)*

Call `upload_object` for **every confirmed file at the same time** — do not wait for one to finish before starting the next:

- `source_gcs_uri`: The URI identified in Step 1a for this file.
- `destination_bucket`: `ag-core-ops-auj0-kb-landing-zone`
- `filename`: The confirmed filename (or the renamed filename if the user chose Rename).
- `path_inside_bucket`: The confirmed `<project_id>` for this file.

Wait for **all** uploads to complete before proceeding to Step 3b.

### Step 3b: Stamp Metadata *(all files launched in parallel simultaneously)*

Once all uploads from Step 3a have finished, call `update_object_metadata` for **every file at the same time**:

```json
{
  "project": "<project_id>",
  "domain": "<domain>",
  "trust-level": "<trust_level>",
  "pii_status": "<Yes or No>"
}
```

Wait for **all** metadata stamps to complete before proceeding to Step 3c.

### Step 3c: Verify Uploads *(all files launched in parallel simultaneously)*

After all metadata stamps from Step 3b have completed, call `read_object` for **every file at the same time**:
- `bucket_name`: `ag-core-ops-auj0-kb-landing-zone`
- `object_name`: `<project_id>/<filename>`

For each file verify **both conditions**:
1. `execution_status == "success"` — the blob is present in the KB landing zone.
2. `metadata.custom_metadata` contains all four required keys: `project`, `domain`, `trust-level`, `pii_status`.

**Automatic recovery (do not ask the user — act immediately):**

- **Object not found** → automatically re-run Step 3a (`upload_object`) for this file, then immediately re-run Step 3b (`update_object_metadata`) for the same file using the confirmed metadata, then call `read_object` again to re-verify. If it passes, include the file in Step 4. If it fails a second time, report the error to the user and ask how they would like to proceed.
- **Metadata keys missing** → automatically re-run Step 3b (`update_object_metadata`) for this file using the full confirmed metadata payload, then call `read_object` again to re-verify. If it passes, include the file in Step 4. If it fails a second time, report which keys are still absent and ask the user how they would like to proceed.
- **Both pass on the first check** → include this file in Step 4's pipeline trigger batch immediately.

Only files that pass verification (either on the first check or after automatic recovery) advance to Step 4.

### Step 4: Trigger Pipeline *(all verified files launched in parallel simultaneously)*

Call `trigger_ekb_pipeline(gcs_uri='<destination_uri_returned_in_Step_3a>')` for **every verified file at the same time** — do not wait for one to finish before starting the next.

- **Note**: The `gcs_uri` MUST be exactly the URI returned by `upload_object` in Step 3a for that file.

**Final Confirmation**: After all pipeline triggers have responded, provide a single consolidated summary:

```markdown
### Ingestion Started
| File | Project | Job ID | Status |
|:---:|:---:|:---:|:---:|
| <file1.pdf> | <project_id> | <job_id> | <current job status> |
| <file2.pdf> | <project_id> | <job_id> | <current job status> |
```

Include a brief summary: how many files are being processed, and whether any have succeeded or failed.

For a single file, use the original single-entry format instead of the table.

### Retry Protocol

When the user asks to retry a failed ingestion (e.g., "retry", "try again", "re-upload"):

1. **Skip Steps 1 and 2 entirely** — file identity and metadata were already confirmed in the original attempt. Do NOT ask the user to re-confirm or re-provide any information.
2. **Start directly at Step 3a**: Re-upload the affected file(s) using the same source URIs, destination bucket, filenames, and project paths from the previous attempt.
3. **Proceed through Steps 3b, 3c, and 4** exactly as defined — stamp metadata, verify, and trigger the EKB pipeline — running all tool calls in parallel.
4. Present the consolidated summary from Step 4 once all pipeline triggers respond.
5. If the retry also fails, report the error clearly and ask the user how they would like to proceed.
