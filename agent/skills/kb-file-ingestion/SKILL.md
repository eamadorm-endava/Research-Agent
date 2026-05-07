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
- [ ] Step 1: Identify and validate all uploaded PDF files
- [ ] Step 2a: Metadata collection — auto-fill from context if available, otherwise ask in one message
- [ ] Step 2b: Semantic project validation + deduplication check (per file, run in parallel)
- [ ] Step 2c: Present confirmation table → handle per-file overrides → await explicit user confirmation
- [ ] Step 3a: Upload files to KB landing zone (all files in parallel)
- [ ] Step 3b: Stamp metadata on uploaded files (all files in parallel, after 3a completes)
- [ ] Step 4: Trigger EKB pipeline (all files in parallel) + consolidated final summary

## Gotchas
- **GCS URIs**: The agent landing zone is always `gs://ai_agent_landing_zone/`. 
- **KB Landing Zone**: The KB ingestion bucket is **`gs://ag-core-dev-fdx7-kb-landing-zone/`**. You MUST use this exact name for the `destination_bucket` to trigger the Service Account authentication switch.
- **Project IDs**: In BigQuery, `project_id` is case-sensitive in some operations but should be checked case-insensitively for duplicates.
- **Job IDs**: Always return the `job_id` from the pipeline response to the user as a confirmation.
- **Proactive Notifications**: The agent core automatically checks pending `job_id`s before every response. You do not need to poll manually; a system update will appear in your history once the job is finished.
- **Parallelism**: Steps 3a, 3b, and 4 each launch ALL their tool calls at the same time. Never loop one-by-one.

## Mandatory Workflow

### Step 1: Identify and Validate the File
1.  Use the `get_artifact_uri` tool to find the URI of the file the user just uploaded.
2.  **Validation**:
    - **File Type**: Ensure every detected file is a **PDF**. For any non-PDF (e.g. `.docx`, `.txt`), inform the user: "Endava's Knowledge Base only accepts PDF documents. Please convert `<filename>` to PDF and upload it again."
    - **Multi-file**: If multiple PDF files exist, list them all and proceed with the full batch — do NOT ask the user to pick one.
    - **Missing**: If no PDF file is found, ask: "Please upload the PDF document(s) you'd like to add to the knowledge base."

### Step 2: Information Gathering, Validation & Confirmation

#### 2a — Metadata Collection

**Auto-fill from context (applies to both single and batch):**

Before asking the user for metadata, check whether you already have project context in the current conversation (e.g., the user mentioned a project name, you retrieved project records earlier, or there is a confirmed `project_id` in the session). If you have enough context to propose values for any of the four metadata fields (Project, Domain, Trust-level, PII Status), pre-fill them and ask the user to confirm rather than asking from scratch:

> "Based on our conversation, I have pre-filled the following metadata. Please confirm or correct any values before I proceed:
> - **Files**: `<file1.pdf>`, `<file2.pdf>`, …
> - **Project**: `<inferred_project>` ← *inferred from context*
> - **Domain**: `<inferred_domain>` ← *inferred from context* (or blank if unknown)
> - **Trust-level**: `<inferred_trust_level>` ← *inferred from context* (or blank if unknown)
> - **PII Status**: `<inferred_pii_status>` ← *inferred from context* (or blank if unknown)
>
> Is everything correct? If anything needs to change, let me know before I continue."

Only ask the full question below when no context is available.

**No context — Single file**: Ask for all metadata in one message immediately after Step 1:

> "Before publishing the file to the EKB, please provide me the following information:
> - **Project the file belongs to**:
> - **Domain**: (`IT` / `Finance` / `HR` / `Sales` / `Executives` / `Legal` / `Operations`)
> - **Trust-level**: (`Published` — verified & ready for company-wide use | `WIP` — draft still being refined | `Archived` — historical reference, no longer active)
> - **PII Status**: Does this document contain any Personally Identifiable Information (names, emails, IDs)?"

**No context — Multiple files (Batch Mode)**: List all detected filenames, then ask for shared metadata in one message:

> "Before publishing those files to the EKB, please provide me the following information:
> - **Files detected**: `<file1.pdf>`, `<file2.pdf>`, … *(list all)*
> - **Project the files belong to**:
> - **Domain**: (`IT` / `Finance` / `HR` / `Sales` / `Executives` / `Legal` / `Operations`)
> - **Trust-level**: (`Published` | `WIP` | `Archived`)
> - **PII Status**: Do any of these documents contain Personally Identifiable Information (names, emails, IDs)?"

#### 2b — Validation (run all checks in parallel for every file simultaneously)

Once the user confirms or provides metadata, launch the following for **all files at the same time**:

1.  **Semantic Project Validation**: Use `ekb_semantic_search(query='<user_input_project_name>')`.
    - If a high-confidence match exists, proceed with that `project_id`.
    - If ambiguous, ask: "I found existing projects that might match: [List]. Is it one of these?"
2.  **Deduplication Check**: For each file, check for duplicate filenames in the confirmed project:
    ```sql
    SELECT filename, domain, classification_tier 
    FROM `knowledge_base.documents_metadata` 
    WHERE project_id = '<confirmed_project>' AND lower(filename) = lower('<uploaded_filename>')
      AND latest = TRUE
    ```
    - If a duplicate is found, ask: "A version of `<filename>` already exists. Should I replace it or would you like to rename this file?"
    - **MANDATORY**: If the user chooses to **REPLACE**, reuse the `domain` and `classification_tier` from the existing record for that file.

#### 2c — Confirmation & Per-File Override

After validation, present a summary table of the full ingestion plan:

| File | Project | Domain | Trust-level | PII |
|:---:|:---:|:---:|:---:|:---:|
| `<file1.pdf>` | `<project_id>` | `<domain>` | `<trust-level>` | Yes / No |
| `<file2.pdf>` | `<project_id>` | `<domain>` | `<trust-level>` | Yes / No |

Then ask *(single file)*:
> "Does everything look correct? If so, I will proceed with the publishing process or let me know if anything needs to change."

Or *(multiple files)*:
> "Should I apply these same metadata values to all files? If any file needs a different project, domain, trust-level, or PII status, please specify the filename and the values that differ. Otherwise I will proceed with publishing all files."

- If the user specifies per-file overrides, update the plan for those files, re-display the corrected table, and ask for final confirmation before continuing.
- Do NOT proceed to Step 3 until the user explicitly confirms.

### Step 3a: Upload Files *(all files launched in parallel simultaneously)*

Call `upload_object` for **every file at the same time** — do not wait for one to finish before starting the next:

For each file use:
- `source_gcs_uri`: The URI identified in Step 1 for this file.
- `destination_bucket`: "ag-core-dev-fdx7-kb-landing-zone"
- `filename`: The confirmed filename.
- `path_inside_bucket`: The confirmed `<project_id>` for this file.

Wait for **all** uploads to complete before proceeding to Step 3b.

### Step 3b: Stamp Metadata *(all files launched in parallel simultaneously)*

Once all uploads from Step 3a have finished, call `update_object_metadata` for **every file at the same time**:

```json
{
  "project": "<project>",
  "domain": "<domain>",
  "trust-level": "<trust_level>",
  "pii_status": "<status>"
}
```

Wait for **all** metadata stamps to complete before proceeding to Step 4.

### Step 4: Trigger Pipeline *(all files launched in parallel simultaneously)*

Call `trigger_ekb_pipeline(gcs_uri='<destination_uri_returned_in_Step_3a>')` for **every file at the same time** — do not wait for one to finish before starting the next.

- **Note**: The `gcs_uri` MUST be exactly the URI returned by the `upload_object` tool in Step 3a for that file.

**Final Confirmation**: After all pipeline triggers have responded, provide a single consolidated summary:

```markdown
### Ingestion Started
| File | Project | Job ID | Status |
|:---:|:---:|:---:|:---:|
| <file1.pdf> | <project_id> | <job_id> | <current job status> |
| <file2.pdf> | <project_id> | <job_id> | <current job status> |

All documents are being processed and will be available in the KB shortly.
```
For a single file, use the original single-entry format instead of the table.
