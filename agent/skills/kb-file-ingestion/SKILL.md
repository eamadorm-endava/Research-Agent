---
name: kb-file-ingestion
description: Orchestrates the ingestion of user-uploaded files into the Enterprise Knowledge Base.
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
or similar requests.

## Progress Tracker
Maintain this state throughout the interaction:
- [ ] Step 1a: Get URIs for all uploads → validate every file is a PDF
- [ ] Step 1b: Read every valid PDF (all in parallel) → extract metadata hints per file
- [ ] Step 2 (background, all in parallel): Merge PDF hints + conversation context → semantic project validation + deduplication check for every file simultaneously
- [ ] Step 2 (user-facing): Present ONE combined message — pre-filled metadata table + any ambiguity/duplicate warnings + confirmation ask
- [ ] Step 2 (await): Wait for explicit user approval covering metadata AND all open questions
- [ ] Step 3a: Upload files to KB landing zone (all files in parallel)
- [ ] Step 3b: Stamp metadata on uploaded files (all files in parallel, after 3a completes)
- [ ] Step 3c: Verify every file — object exists AND metadata is complete (all files in parallel)
- [ ] Step 4: Trigger EKB pipeline for verified files only + consolidated final summary

**On retry**: Steps 1 and 2 are already complete — jump directly to Step 3a using the previously confirmed file URIs and metadata.

## Gotchas
- **GCS URIs**: The agent landing zone is always `gs://ai_agent_landing_zone/`.
- **KB Landing Zone**: The KB ingestion bucket is **`gs://ag-core-dev-fdx7-kb-landing-zone/`**. You MUST use this exact name for the `destination_bucket` to trigger the Service Account authentication switch.
- **Project IDs**: In BigQuery, `project_id` is case-sensitive in some operations but should be checked case-insensitively for duplicates.
- **Job IDs**: Always return the `job_id` from the pipeline response to the user as a confirmation.
- **Parallelism**: Steps 1b, 3a, 3b, 3c, and 4 each launch ALL their tool calls at the same time. Never loop one-by-one.

## Mandatory Workflow

### Step 1: Identify, Validate and Read Files

#### 1a — Identify & Validate

1. Call `get_artifact_uri` for every file the user uploaded.
2. For each file:
   - If not a PDF (e.g. `.docx`, `.txt`): inform the user "Endava's Knowledge Base only accepts PDF documents. Please convert `<filename>` to PDF and upload it again." Exclude it from the batch.
   - If no PDFs are found at all: ask "Please upload the PDF document(s) you'd like to add to the knowledge base."
3. Proceed only with the confirmed PDF files.

#### 1b — Read PDF Content *(all valid PDFs launched in parallel simultaneously)*

For every confirmed PDF call `import_gcs_to_artifact(gcs_uri=<uri>, mime_type="application/pdf")` then `load_artifacts` to read its content.

From each file, extract hints for the four required metadata fields:
- **Project**: Look for engagement names, client names, or project identifiers in the title, cover page, headers, footers, or document properties.
- **Domain**: Infer from subject matter — technical/engineering content → `IT`; financial reports/budgets → `Finance`; HR policies/org content → `HR`; sales/commercial material → `Sales`; executive-level strategy or leadership → `Executives`; contracts or compliance → `Legal`; process or ops documentation → `Operations`.
- **Trust-level**: Look for status indicators — "Final", "Approved", "Published" → `Published`; "Draft", "Work in Progress", "WIP", or "v0.x" → `WIP`; "Deprecated", "Superseded", or "Archive" → `Archived`.
- **PII**: `Yes` if the document contains visible names, emails, ID numbers, phone numbers, or any direct personal identifiers; otherwise `No`.

If a file cannot be read (error from `import_gcs_to_artifact`), note the failure, leave all four fields blank for that file, and continue.

### Step 2: Background Validation → Single User-Facing Message

#### Background *(run immediately after Step 1b, all checks launched in parallel)*

Merge the hints extracted in Step 1b with any values present in the current conversation history. Conversation context takes precedence over PDF extraction when both sources provide a value for the same field.

1. **Semantic Project Validation** — for every unique project name inferred, call `ekb_semantic_search(query='<inferred_project_name>')`:
   - High-confidence single match → resolve to that `project_id`.
   - Multiple plausible matches → collect the candidates; surface them as an inline ⚠️ question in the user-facing message.
   - No match → leave the project cell blank; flag it as missing input in the message.

2. **Deduplication Check** — for each file whose project resolved to a confirmed `project_id`, run:
   ```sql
   SELECT filename, domain, classification_tier
   FROM `knowledge_base.documents_metadata`
   WHERE project_id = '<confirmed_project_id>'
     AND lower(filename) = lower('<uploaded_filename>')
     AND latest = TRUE
   ```
   - Duplicate found → record the existing `domain` and `classification_tier`; surface a replace-or-rename question in the user-facing message.
   - No duplicate → no extra question for this file.
   - If the project was ambiguous (unresolved), skip the dedup check for that file — it will run after the user confirms the project.

#### User-Facing Message *(one message only, sent after all background checks complete)*

Send a single message with this exact structure:

> "Based on the contents of the files, I have pre-filled the metadata to be used. Please let me know if it's correct or if you want to make changes, and answer any questions below before I proceed:
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
>
> **Trust-level options**: 
>   - `Published` — verified & ready for company-wide use 
>   - `WIP` — draft still being refined 
>   - `Archived` — historical reference, no longer active
>
> *(question blocks appear here only when there are open issues — see rules below, a bullet point per question)*
>
> Please confirm the metadata and answer any question(s) above to proceed."

**Cell formatting rules:**
- Write only the metadata value in every cell, regardless of how it was obtained.
- If a value cannot be inferred from either source, use `—` with no additional text.

**⚠️ Issue blocks** (append below the table, one block per open issue; omit entirely if no issues exist):

For an ambiguous project match:
> ⚠️ **Project unclear for `<filename>`**: I found multiple possible matches in the EKB. Is it one of these?
> - `<Project Name A>` (ID: `<id_a>`)
> - `<Project Name B>` (ID: `<id_b>`)

For a duplicate filename:
> ⚠️ **Duplicate detected for `<filename>`**: A version already exists in `<project_id>` (Domain: `<existing_domain>`, Trust-level: `<existing_tier>`). Should I:
> - **Replace** the existing file (its domain and trust-level will be preserved from the existing record)
> - **Rename** `<filename>` — please provide the new filename

**MANDATORY — Replace rule**: If the user chooses Replace for any file, override that file's `domain` and `trust-level` in the ingestion plan with the values fetched from the existing BigQuery record. Do NOT use inferred or user-typed values for those two fields.

#### Awaiting User Response

Do NOT start Step 3a until all three conditions are met:
1. The user has explicitly confirmed the metadata table or provided corrections.
2. Every ⚠️ duplicate question has been answered (Replace, or Rename with a new filename).
3. Every blank (`—`) project cell has been resolved to a confirmed `project_id`.

If the user corrects a project name that was previously unresolved or wrong, re-run `ekb_semantic_search` for the corrected name and, if it resolves, run the dedup check for that file before proceeding.

If the user requests per-file metadata overrides, update the affected rows, re-display the corrected table, and ask for confirmation again before continuing.

### Step 3a: Upload Files *(all files launched in parallel simultaneously)*

Call `upload_object` for **every file at the same time** — do not wait for one to finish before starting the next:

- `source_gcs_uri`: The URI identified in Step 1a for this file.
- `destination_bucket`: `ag-core-dev-fdx7-kb-landing-zone`
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
- `bucket_name`: `ag-core-dev-fdx7-kb-landing-zone`
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
