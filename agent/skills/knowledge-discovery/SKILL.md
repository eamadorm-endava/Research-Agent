---
name: knowledge-discovery
description: Expert protocol for high-fidelity data retrieval and analysis using Contextual Anchoring and Parallel Discovery.
---

## Mandatory Execution Mode
Trigger this skill for any research task or when the user's query is broad or vague. Use this to establish a factual baseline across all data sources.

## BigQuery Query Protocol
This protocol applies **every time** you are about to call `execute_query`, regardless of which phase you are in.

1.  **Discover tables** (skip if already done this session for the same dataset): Call `list_tables` to confirm which tables exist inside the target dataset.
2.  **Fetch and cache schema** (skip if already fetched this session for the same table): Call `get_table_schema` for each table you intend to query. Store the returned field names and types in your working memory — do **not** call `get_table_schema` again for the same table later in the same session.
3.  **Construct the query**: Build the SQL using only column names confirmed in step 2. Never guess column names.
4.  **Execute**: Call `execute_query` with the validated query.

## Discovery Protocol

### Phase 1: Contextual Anchoring (The Hook)
1.  **Semantic Search**: Execute `ekb_semantic_search`.
2.  **Anchor Extraction**: Build a "Context Graph" from the results:
    -   **Identities**: `project_name`, `project_id`, `document_id`, and `filename`.
    -   **Context**: Capture the `document_summary` or `description`. These snippets are vital for identifying additional keywords for Phase 2.
    -   **Entities**: Company names (clients/partners), technologies, and technical stacks.
    -   **Relational Mapping**: If a company is identified, immediately pivot to find the projects they are involved in. Use these project names as primary anchors for Phase 2 discovery across all sources.
    -   **People**: `uploader_email` and key stakeholders mentioned in descriptions.
    -   **Locations**: `gcs_uri` (essential for technical deep-dives).
3.  **Expansion**: If results are narrow, broaden the search using the extracted entities and keywords to find related entries before moving to Phase 2.
    -   **Zero-Result Fallback**: If `ekb_semantic_search` returns no results at all, do not stop. Extract keywords directly from the user's original prompt (company names, project names, technologies, people, dates) and use those as Phase 2 anchors for Drive and Calendar. Skip the BigQuery `documents_metadata` query in this case — there is no project context to anchor it against.

### Phase 2: Parallel Context Acquisition (Broad Search)
Maximize information gathering by querying multiple sources in parallel.
*Efficiency Rule: DO NOT repeat the same tool call with the same parameters in the same session. Aim to find core data in the first turn. For concurrent request limits per source, follow the source-specific protocol (Calendar: 2 per wave; Drive: up to 9 in Wave 1, 3 in Wave 2).*

1.  **Calendar (Broad Temporal Discovery)** — follow the CALENDAR SEARCH PROTOCOL defined in the system prompt exactly:
    -   **Pre-condition**: Call `get_current_time` before the first calendar call of any new user request. Do NOT call it more than once per turn.
    -   **Wave 1 — Broad Baseline (two parallel calls, no `query`)**: `list_calendar_events` twice simultaneously — Past: `date_min=[today-1month]`, `date_max=[today]`, `sort_order="desc"` | Future: `date_min=[today]`, `date_max=[today+1month]`, `sort_order="asc"`. After results arrive, scan event `title` and `description` fields internally for entities from Phase 1 (project names, company names, people). If relevant events found → Event Enrichment. If not → Wave 2.
    -   **Wave 2 — Extended Range (two parallel calls, no `query`, only if Wave 1 found nothing relevant)**: Past: `date_min=[today-6months]`, `date_max=[today]`, `sort_order="desc"` | Future: `date_min=[today]`, `date_max=[today+6months]`, `sort_order="asc"`. Same internal filtering on `title` and `description`. If relevant events found → Event Enrichment. If not → Wave 3.
    -   If no relevant events are found after Wave 2, stop calendar searches and move to Phase 3. Maximum 4 `list_calendar_events` calls per run.
    -   **Event Enrichment**: `CalendarEvent` already contains all primary metadata — extract directly: `attendees` (email, display_name, response_status, organizer), `attachments` (title, file_url, file_id), `meet_session` (joining_url, meeting_code). Only make additional calls when explicitly needed: attachment content → `get_file_text(file_id=<attachment.file_id>)`; session join/leave times → `list_meet_sessions(meeting_code)` → `list_meet_participants(meet_session_id)`; recording/transcript → only when user explicitly asks.
    -   **Hard Rules**: Never include a `query` parameter in any calendar call. Always provide `date_min` and `date_max` together. Maximum 4 `list_calendar_events` calls per user request. Never call `list_meet_participants` without a `meet_session_id` from a prior `list_meet_sessions` call. Never call `get_file_text` for an attachment without using `attachment.file_id`.
    -   **Display**: Present each relevant event using the CALENDAR EVENT DISPLAY FORMAT defined in the system prompt (Title, Time, Attendees, Meet link, Attachments, Description).
2.  **BigQuery (Structural Context)**:
    -   **MANDATORY**: Follow the BigQuery Query Protocol above before querying. Target the `documents_metadata` table inside the `knowledge_base` dataset.
    -   **Data Capture**: Retrieve and store all metadata, especially the **document summary/description**, linked to the identified project, domain, or company.
3.  **Google Drive (Personal Context - Two-Wave Parallel Search)**:
    -   **Keyword Extraction**: Collect all useful nouns from Phase 1 anchors and the user's original prompt — project names, company names, technologies, people, product names, and other domain-specific terms. **Always exclude intent words like "duration", "status", or "summary"**.
    -   **Keyword Decomposition (MANDATORY before Wave 1)**:
        -   **Project names**: Split word-by-word; drop generic words (`Project`, `Initiative`, `Program`) unless distinctive. `"Project Alpha"` → `["Alpha"]`; `"GCP Integration"` → `["GCP", "Integration"]`.
        -   **Company names**: Strip generic suffixes (`Inc`, `Corp`, `Ltd`, `LLC`, `S.A.`, `Co.`, `Group`, `Holdings`). For multi-word clean names, generate one keyword per meaningful word AND the full clean name. `"Innovation Inc"` → `["Innovation"]`; `"GP Morgan"` → `["GP", "Morgan", "GP Morgan"]`.
        -   **Relational cross-reference**: Before building the keyword list, explicitly map the project names found in Phase 1 to any companies, persons, or tech stacks associated with them. Add all of those as additional keywords for Drive — the project–company relationship is a primary signal for finding relevant files.
    -   **Wave 1 — Broad Parallel Discovery (all calls launched simultaneously)**: Launch up to **9 `list_files` calls in parallel**, organized into three fixed slots:
        -   **Company/client slot**: up to 3 calls, one per company keyword. Always populated when companies are present.
        -   **Project slot**: up to 3 calls, one per project keyword. Always populated when projects are present.
        -   **Technology slot**: up to 3 calls, one per technology keyword. Populated only after the above two slots are filled.
        -   **Minimum**: when both company and project keywords exist, at least 6 calls must be launched. Do NOT read file contents in this wave.
        -   From every result, capture and store in the candidate pool: `file_id`, `file_name`, `folder_path`, `mime_type`, `created_by`. The `file_id` field is the only accepted identifier for `get_file_text`.
        -   **Inline triage** (after all Wave 1 results arrive): classify each file as **High** (filename contains a project, company, or technology term), **Medium** (plausibly related), or **Low** (unrelated — deprioritize).
    -   **Wave 2 — Relational Refinement (run in parallel, always follows Wave 1)**: Using the relationship map from Phase 1 and the Wave 1 triage results, search for gaps:
        -   If Wave 1 found files via a project keyword, search the associated company keywords not yet used — and vice versa.
        -   Use remaining decomposed keywords from the list not consumed in Wave 1.
        -   Extract any new candidate terms surfaced by Wave 1 filenames (aliases, codes, short names visible in results).
        -   Launch up to **3 additional `list_files` calls simultaneously**. Capture `file_id`, `file_name`, `folder_path`, `mime_type`, `created_by` and merge into the triage pool, re-applying High/Medium/Low.
    -   **Exclusion Rule**: Never use intent keywords (e.g., "duration", "project length", "status") as `file_name` filters. Focus on nouns that likely appear in filenames.
4.  **GCS (Raw Data Reference)**:
    -   Identify and store specific `gcs_uri` references for high-relevance files found in the metadata.

### Phase 3: Synthesis & Targeted Deep Dive (Escalation Path)
If high-level summaries or metadata are insufficient for a comprehensive answer, follow this strict escalation order:

1.  **Level 1: EKB Deep-Dive (GCS)**:
    -   Use `read_object` to retrieve metadata (specifically the `mime_type`) and then `import_gcs_to_artifact` to analyze the full content of high-relevance `gcs_uri` references found in Phase 1 and 2.
    -   Prioritize technical specifications, architecture diagrams, and project charters stored in EKB.
2.  **Level 2: Calendar Deep-Dive (Personal Context)**:
    -   From the relevant events found in Phase 2, inspect `attachments` (each has a `file_id` and `title`) and the `description` field for documents, links, or referenced material.
    -   For each attachment whose content is relevant: call `get_file_text(file_id=<attachment.file_id>)` to read it via Drive — the `file_id` from `EventAttachment` is a Drive file ID and requires no extra lookup.
    -   Also check the event `description` for external links or GCS URIs and retrieve those using the appropriate tool.
3.  **Level 3: Drive Iterative Discovery**:
    -   **Step 1 (Read)**: Sort the candidate pool from Phase 2 by triage class — High first, then Medium. Call `get_file_text(file_id=<file_id>)` for at most **5 files per turn**, running all calls in parallel. Never read Low-classified files unless the pool is exhausted.
    -   **Step 2 (Evaluate)**: If the information is found, stop and synthesize.
    -   **Step 3 (Pivot & Repeat)**: If not found, extract new keywords from the text read (e.g., project codes, aliases, or stakeholders) and run one additional Wave 1 cycle with those keywords. Maximum 1 extra cycle. Ensure each search uses unique keywords to avoid redundant results.
4.  **Level 4: Relationship Fallback (Implicit Mapping)**:
    -   If direct project/company links are missing, analyze EKB metadata (descriptions, summaries, and tech stacks) for shared technologies, industry themes, or generalities.
    -   Use these broader themes to re-evaluate the broad results found in Phase 2 (Calendar/Drive) to identify high-fidelity implicit relationships.
5.  **Level 5: Final Conclusion**:
    -   Produce the standard output structure with `No information found` under any section where data is missing.
    -   **MANDATORY**: Your response MUST include the `## Extend Search?` section defined at the end of the MANDATORY OUTPUT STRUCTURE. This section is not optional at Level 5 — if it is missing, the task is incomplete.
    -   Do not continue searching without the user's input. Do not hallucinate.

### MANDATORY OUTPUT STRUCTURE
Before writing the response, classify the question:
-   **Concise Mode**: the question has a clear, narrow answer (a single fact, name, date, count, status, or yes/no). Use this mode for targeted lookups.
-   **Full Report Mode**: the answer requires synthesizing information across multiple sources, documents, or time periods. Use this mode for broad or exploratory research.

---

#### Concise Mode
Respond directly in plain prose (1–3 sentences). Then append only the `## References` table (see format below). Skip all other sections.

---

#### Full Report Mode
Cross-correlate all findings into a unified narrative before writing the response. Follow this exact section order. Omit a section only if genuinely no data exists for it — in that case write `No information found` under that heading, do not skip the heading entirely.

**Summary** *(always present)*
1–2 paragraphs. Brief context of what was found, the topic, and its relevance. No bullet points here.

---

**## Key Points**
Bullet list of the most important facts, decisions, dates, and findings extracted from the sources.

---

**## Stakeholders**
Bullet list of people involved: name, role or relationship to the topic, and contact email when available.

---

**## Upcoming Meetings**
List ONLY meetings occurring after the current date that are directly related to the project, company, or topic the user asked about. Render each event using the CALENDAR EVENT DISPLAY FORMAT (Title, Time, Attendees, Meet link, Attachments, Description — `Meeting intent not specified` if description is absent). Separate events with `---`.
If none found: `No upcoming meetings found for this topic.`

---

**## Previous Meetings**
List meetings from the past window (Phase 2 Calendar search) that are related to the project, company, or topic the user asked about. Render each event using the CALENDAR EVENT DISPLAY FORMAT (Title, Time, Attendees, Meet link, Attachments, Description — `Meeting intent not specified` if description is absent). Separate events with `---`.
If none found: `No recent meetings found for this topic.`

---

**## Extend Search?** *(include ONLY when Level 5 is reached — all standard sources exhausted with no relevant results)*
Begin with one sentence stating which sources were searched and what terms were used. Then include this question verbatim:

> "I have searched the Enterprise Knowledge Base, Google Calendar, and Google Drive using the available context and found no matching data. Would you like me to extend the search to your personal GCS buckets or BigQuery tables? If yes, please share the bucket name, path prefix, or table/dataset identifier and I will search there directly."

This section MUST appear after `## References` at Level 5. Omitting it when Level 5 is reached means the task is incomplete.

---

**## References** *(both modes — omit entirely if no referenceable sources were used)*
If the answer was produced entirely from conversational context, general knowledge, or tool outputs that do not correspond to a specific file, document, or calendar event (e.g., a direct BigQuery aggregate result with no linked document), **omit this section completely** — do not render the heading or an empty table.

Otherwise, include a Markdown table with ONLY the files, documents, and events from which data was explicitly extracted to produce this response. NEVER include broad discovery results or unused tool outputs.

| Source | Filename | Owner | Created at / Last Update |
|:---:|:---:|:---:|:---:|
| EKB / Drive / Cloud Storage / BigQuery (`dataset.table`) | Human-readable file or event name | Author email or display name | `YYYY-MM-DD` |

-   **Source**: one of `EKB`, `Drive`, `Cloud Storage`, or `BigQuery (dataset.table)` — use the most specific label, e.g. `BigQuery (knowledge_base.documents_metadata)`.
-   **Filename**: human-readable name or event title. NEVER show raw IDs, hashes, or GCS URIs.
-   **Owner**: uploader email, document owner, or event organizer. Use `Unknown` if unavailable.
-   **Created at / Last Update**: `YYYY-MM-DD`. Use `Unknown` if unavailable.