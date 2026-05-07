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
- [ ] Step 2a: Collect shared metadata (single message for all files)
- [ ] Step 2b: Semantic project validation + deduplication check (per file)
- [ ] Step 2c: Present confirmation table → handle per-file overrides → await explicit user confirmation
- [ ] Step 3: Relocate and stamp metadata (parallel — all files simultaneously)
- [ ] Step 4: Trigger EKB pipeline (parallel — all files simultaneously) + consolidated final summary

## Gotchas
- **GCS URIs**: The agent landing zone is always `gs://ai_agent_landing_zone/`. 
- **KB Landing Zone**: The KB ingestion bucket is **`gs://ag-core-dev-fdx7-kb-landing-zone/`**. You MUST use this exact name for the `destination_bucket` to trigger the Service Account authentication switch.
- **Project IDs**: In BigQuery, `project_id` is case-sensitive in some operations but should be checked case-insensitively for duplicates.
- **Job IDs**: Always return the `job_id` from the pipeline response to the user as a confirmation.
- **Proactive Notifications**: The agent core automatically checks pending `job_id`s before every response. You do not need to poll manually; a system update will appear in your history once the job is finished.

## Mandatory Workflow

### Step 1: Identify and Validate the File
1.  Use the `get_artifact_uri` tool to find the URI of the file the user just uploaded.
2.  **Validation**:
    - **File Type**: Ensure every detected file is a **PDF**. For any non-PDF (e.g. `.docx`, `.txt`), inform the user: "Endava's Knowledge Base only accepts PDF documents. Please convert `<filename>` to PDF and upload it again."
    - **Multi-file**: If multiple PDF files exist, list them all and proceed with the full batch — do NOT ask the user to pick one.
    - **Missing**: If no PDF file is found, ask: "Please upload the PDF document(s) you'd like to add to the knowledge base."

### Step 2: Information Gathering, Validation & Confirmation

#### 2a — Metadata Collection

**Single file**: Ask for all metadata in one message immediately after Step 1:

> "Before publishing the file to the EKB, please provide me the following information:
> - **Project the file belongs to**:
> - **Domain**: (`IT` / `Finance` / `HR` / `Sales` / `Executives` / `Legal` / `Operations`)
> - **Trust-level**: (`Published` — verified & ready for company-wide use | `WIP` — draft still being refined | `Archived` — historical reference, no longer active)
> - **PII Status**: Does this document contain any Personally Identifiable Information (names, emails, IDs)?"

**Multiple files (Batch Mode)**: List all detected filenames, then ask for shared metadata in one message:

> "Before publishing those files to the EKB, please provide me the following information:
> - **Files detected**: `<file1.pdf>`, `<file2.pdf>`, … *(list all)*
> - **Project the files belong to**:
> - **Domain**: (`IT` / `Finance` / `HR` / `Sales` / `Executives` / `Legal` / `Operations`)
> - **Trust-level**: (`Published` | `WIP` | `Archived`)
> - **PII Status**: Do any of these documents contain Personally Identifiable Information (names, emails, IDs)?"

#### 2b — Validation (run for every file)

Once the user provides the information, perform the following in sequence:

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

### Step 3: Relocation & Stamping *(execute in parallel for all files in the confirmed batch)*
1.  **Move File**: Use `upload_object` (from GCS MCP) to copy the file using these parameters:
    - `source_gcs_uri`: The URI identified in Step 1 for this file.
    - `destination_bucket`: "ag-core-dev-fdx7-kb-landing-zone"
    - `filename`: The confirmed filename.
    - `path_inside_bucket`: The confirmed `<project_id>` for this file.
    - **Note**: The relocation process automatically preserves the source metadata.
2.  **Stamp Metadata**: Use `update_object_metadata` (GCS) to attach the confirmed metadata for this file. This will be **merged** with existing metadata:
    ```json
    {
      "project": "<project>",
      "domain": "<domain>",
      "trust-level": "<trust_level>",
      "pii_status": "<status>"
    }
    ```

### Step 4: Trigger Pipeline *(execute in parallel for all files in the confirmed batch)*
1.  Call `trigger_ekb_pipeline(gcs_uri='<destination_uri_returned_in_Step_3>')` for each file simultaneously.
    - **Note**: This MUST be exactly the same URI returned by the `upload_object` tool for that file.
2.  **Final Confirmation**: After all files have been processed, provide a single consolidated summary:
    ```markdown
    ### Ingestion Started
    | File | Project | Job ID | Status |
    |:---:|:---:|:---:|:---:|
    | <file1.pdf> | <project_id> | <job_id> | <current job status> |
    | <file2.pdf> | <project_id> | <job_id> | <current job status> |

    All documents are being processed and will be available in the KB shortly.
    ```
    For a single file, use the original single-entry format instead of the table.
