---
name: knowledge-discovery
description: Expert protocol for high-fidelity data retrieval and analysis using Contextual Anchoring and Parallel Discovery.
---

## Pre-Search Validation

Before doing anything else, check whether the user has clearly stated what they want to search for.

**A query is unclear when it:**
- Expresses intent without a topic (e.g., "search the EKB", "do a research", "look it up", "find something")
- Names only a source, not a subject (e.g., "check the knowledge base", "query the EKB")
- Is too vague to form a meaningful search (e.g., "find documents", "search for info")

**When the query is unclear**, stop and ask:
> "What topic, document, project, or information would you like me to search for?"

Do not guess, infer, or proceed with a search. Wait for the user's answer before continuing.

**When the query is clear** (contains at least one concrete subject — a project name, company, person, technology, document title, or specific question), proceed immediately to Intent Classification below.

---

## Intent Classification
Before any retrieval, classify the user's request into one of two modes:

**Targeted Mode** — user asks for a precise, narrow fact, or mentions a specific document:
- "What is the project duration?"
- "Give me the start date of the SoW"
- "What does the contract say about pricing?"
- "Search for a file called Innovation SoW and tell me the main points of it"
- "What budget was approved for project X?"
→ Converge fast. Use the two-wave EKB search + GCS long-context escalation.

**Discovery Mode** — user asks a broad or exploratory question:
- "Tell me about project X"
- "What do we know about company Y?"
- "Find all documents related to Z"
- "Summarize everything we have on this topic"
- "Give me all the projects that are related with the technology X"
- "Tell me all the projects related to the specific sector Y"
→ Cast a wide net across all sources. Synthesize across EKB, Calendar, BQ, and Drive.

---

## Targeted Mode Protocol

### Wave 1 — Broad Semantic + Keyword Discovery
Run the following calls simultaneously:

**1a. Semantic Search** — `ekb_semantic_search`:
- `query`: user's keywords or document name — strip intent words (`"give me"`, `"what is"`, `"duration"`, `"status"`, `"date"`, `"summary"`)
- `top_k`: `15`

Do NOT include `filename`, `domain`, `project_filter`, or `trust_level`.

**1b. Keyword Search** — `ekb_keyword_search`:
- `keyword`: the primary entity from the user's query — a technology name, sector, company, or person. Strip all intent words and keep only a single word (e.g., `"React"`, `"healthcare"`, `"banking"`, `"Acme"`).

**1c. Calendar Search** — Follow the **CALENDAR SEARCH PROTOCOL** defined in the system prompt exactly.

**After they complete — merge and store:**
- Build a unified file pool: combine all `filename` values from both results, deduplicated.
- From semantic results, also extract and store: `gcs_uri`, `chunk_data`, `document_summary`, `domain`.
- From keyword results, also extract and store: `gcs_uri`, `uploader_email`, `description`.
- Files that appear in both results are the highest-confidence anchors and must be ranked first for Wave 2.

**Zero-result fallback rules:**
- Both return zero → skip Wave 2 and GCS Long Context. Proceed immediately to Calendar Search Protocol + Drive Search Protocol in parallel. **Keyword source for Drive**: extract entities (companies, projects, technologies, people) directly from the user's original prompt — do not wait for EKB results. These user-prompt keywords are the primary input for Drive (Stage 0 entity extraction). Do not use EKB-derived terms as input because there are none.
- Only `ekb_semantic_search` returns zero → use keyword search results as the sole anchor pool and proceed to Wave 2 normally.
- Only `ekb_keyword_search` returns zero → proceed to Wave 2 using semantic results only.

### Wave 2 — Per-File Focused Search (only if Wave 1 returned results)
Select the top 3 most relevant files from Wave 1, ranked by ascending cosine distance. For each, launch one `ekb_semantic_search` call. Run all simultaneously:
- `query`: the user's actual information need — what they want to know, not the filename
- `filename`: exact verbatim value from the `filename` field of a Wave 1 result — never paraphrase or rewrite
- `top_k`: `30`

Run the **DRIVE SEARCH PROTOCOL** (from the system prompt) in parallel with Wave 2, starting immediately after Wave 1 completes. Drive runs regardless of Wave 1 outcome — it is never skipped, even when EKB returned results. **Keyword priority for Drive**: first use terms extracted from the user's original prompt (company names, project names, technologies, people); then supplement with any entities derived from Wave 1 EKB results.

**Hard Rules:**
- Run all Wave 2 calls simultaneously.
- `filename` MUST come verbatim from a prior `ekb_semantic_search` result `filename` field in this session. Never use user's phrasing.
- `top_k` must be `30` in Wave 2 to maximize chunk coverage per file.

### GCS Long Context (only if Wave 1 + Wave 2 chunks are insufficient)
Trigger ONLY when both waves returned results but the specific data was NOT found within the returned chunks. Do NOT trigger if Wave 1 returned zero results — go to Drive Search instead.

For the top 3 files used in Wave 2, run all steps in parallel (following the **GCS FILE READING RULE** from the system prompt):
1. Parse each `gcs_uri` → `bucket_name` (everything between `gs://` and the first `/`) and `object_name` (everything after that first `/`).
2. Call `read_object(bucket_name=<bucket_name>, object_name=<object_name>)`. The system wrapper will automatically intercept this call and load the file natively into your context.

### Drive Search (Targeted Mode)
Drive search always runs — it is not conditional on EKB results. It runs in parallel with Wave 2 (see above). Follow the **DRIVE SEARCH PROTOCOL** defined in the system prompt. **Keyword priority for Stage 0 entity extraction and Stage 1 keyword decomposition**:
1. **Primary**: entities and keywords extracted directly from the user's original prompt (companies, projects, technologies, people).
2. **Supplementary**: entities found in Wave 1 / Wave 1.5 EKB results — add these to the keyword pool after user-prompt extraction to expand coverage.
3. **EKB empty**: if Wave 1 returned zero results, proceed with user-prompt keywords only.

---

## Discovery Mode Protocol

### Phase 1: Contextual Anchoring (The Hook)
1. **Parallel Search**: Run all three calls simultaneously:

   **1a. Semantic Search** — `ekb_semantic_search`:
   - `query`: user's natural language question
   - `top_k`: `10`

   Never add `filename`, `domain`, `project_filter`, or `trust_level`.

   **1b. Keyword Search** — `ekb_keyword_search`:
   - `keyword`: the primary entity from the user's query — a technology name, sector, company, or person. Strip all intent words and keep only a single word (e.g., `"React"`, `"healthcare"`, `"banking"`, `"Acme"`).

   **1c. Calendar Search** — Follow the **CALENDAR SEARCH PROTOCOL** defined in the system prompt exactly.

2. **Anchor Extraction**: Build a "Context Graph" from the merged results of the EKB calls:
   - **Identities**: `filename`, `gcs_uri`, `document_summary` / `description`.
   - **Context**: `description` — key for generating Phase 2 Drive keywords.
   - **Entities**: company names (clients/partners), technologies, technical stacks.
   - **Relational Mapping**: map project names to their associated companies and tech stacks — use these as primary anchors for Phase 2 Drive and Calendar searches.
   - **People**: `uploader_email` and stakeholders mentioned in summaries.
   - **Locations**: `gcs_uri` values (for GCS deep-dive in Phase 3 Level 1).

3. **Expansion**: If results are narrow, broaden using extracted entities before moving to Phase 2.
   - **Zero-Result Fallback**: If both searches return no results, extract keywords directly from the user's original prompt (company names, project names, technologies, dates, people) and use those as Phase 2 anchors. Skip Phase 2b (no BQ project context to anchor against).
   - If only one of the two searches returns results, use the successful search results as anchors for Phase 2.

### Phase 2: Parallel Context Acquisition (Broad Search)

Launch all the following concurrently. *Efficiency Rule: never repeat the same tool call with the same parameters in the same session.*

**2a. Google Cloud Storage** — List all blobs in personal buckets (excluding any bucket belonging to the EKB domain). No content is fetched; only file names and hierarchical paths are collected.

**2b. BigQuery (Personal Datasets)** — List all tables in personal datasets (excluding the `ekb_knowledge_base` dataset). Only table names and brief schema summaries are returned.

**2c. Google Drive** — Follow the **DRIVE SEARCH PROTOCOL** defined in the system prompt (Stage 0 through Wave 1 only). Do NOT execute Stage 2 file reading in Phase 2 — file reading is deferred to Phase 3 Level 3. Keyword priority remains: primary entities from the user's original prompt, supplemented by any entities discovered in Phase 1. If Phase 1 returned zero results, proceed with user-prompt keywords only.

### Phase 3: Synthesis & Targeted Deep Dive (Escalation Path)

**Level 1: EKB Deep-Dive (GCS)**
For the top 3 high-relevance `gcs_uri` values from Phase 1, run in parallel (following the **GCS FILE READING RULE** from the system prompt):
1. Parse each `gcs_uri` → `bucket_name` (everything between `gs://` and the first `/`) and `object_name` (everything after).
2. Call `read_object(bucket_name=<bucket_name>, object_name=<object_name>)`. The system wrapper will automatically intercept this call and load the file natively into your context.

**Level 2: Calendar Deep-Dive (Personal Context)**
From relevant events found in Phase 1, apply the Selective Attachment Reading rule (from the **CALENDAR SEARCH PROTOCOL** in the system prompt): call `get_file_text(file_id=<EventAttachment.file_id>)` only when `EventAttachment.title` or `CalendarEvent.description` contains a term directly relevant to the query.

**Level 3: Drive Iterative Discovery**
Execute Stage 2 of the **DRIVE SEARCH PROTOCOL** (Prioritized File Reading) against the candidate pool built in Phase 2c: High-triage files first, then Medium. At most 5 `get_file_text` calls per turn, all in parallel. If answer not found, extract new keywords from text and run one additional Wave 1 cycle. Maximum 1 extra cycle.

**Level 4: Final Conclusion**
Produce the standard output. Write `No information found` under any section where data is missing. The `## Extend Search?` section from **Final Escalation** below MUST appear — omitting it when Level 4 is reached means the task is incomplete.

---

## Cross-Mode Fallback

**Targeted → Discovery Fallback:**
If Targeted Mode has exhausted all steps without finding the answer, continue with Discovery Mode's unique steps — skipping any tool calls already made:
- Run Phase 2b BQ `documents_metadata` query if not already executed.
- Re-run Drive search with full keyword decomposition if the entity map differs meaningfully from keywords already used. Do not repeat identical `list_files` calls.
- Do NOT repeat `ekb_semantic_search`, `ekb_keyword_search`, `get_current_time`, or `list_calendar_events` calls already made.

**Discovery → Targeted Fallback:**
If Discovery Mode has exhausted all phases (Phase 1 through Level 3) without finding the answer, run Targeted Mode's unique steps — skipping any tool calls already made:
- Wave 2 per-file EKB searches (`top_k=30`) using the top 3 filenames confirmed in Phase 1 or Level 1 results.
- GCS Long Context for those 3 files if their content was not already loaded in Level 1.
- Do NOT repeat Wave 1, calendar calls, Drive calls, or BQ calls already made.

---

## Final Escalation
Trigger ONLY after both modes (including their cross-mode fallbacks) are fully exhausted.

Produce the standard output with `No information found` under all sections, then append the mandatory `## Extend Search?` section verbatim:

> "I have searched the Enterprise Knowledge Base, Google Calendar, Google Drive, and BigQuery using the available context and found no matching data. Would you like me to extend the search to your personal GCS buckets or BigQuery tables? If yes, please share the bucket name, path prefix, or table/dataset identifier and I will search there directly."

When the user provides a personal GCS target: use `list_objects(bucket_name=<name>, prefix=<prefix>)` to list objects, then follow the GCS FILE READING RULE to load relevant files.
When the user provides a personal BQ target: follow the BIGQUERY QUERY PROTOCOL using `list_datasets` + `list_tables` + `execute_query`.

---

## Mandatory Output Structure
Before writing the response, classify the question:
- **Concise Mode**: clear, narrow answer (a single fact, name, date, count, status, or yes/no).
- **Full Report Mode**: answer requires synthesizing across multiple sources, documents, or time periods.

---

#### Concise Mode
Respond directly in plain prose (1–3 sentences). Always append the `## References` table when any data source was used — never omit it. Skip all other sections.

---

#### Full Report Mode
Cross-correlate all findings into a unified narrative before writing. Follow this exact section order. If genuinely no data exists for a section, write `No information found` under that heading — do not skip it. **Exception: the `## Upcoming Meetings` and `## Previous Meetings` sections** — omit both entirely if no calendar search was executed or if calendar searches returned no events relevant to the topic. Do not render these sections with placeholder text in that case.

**Summary** *(always present)*
1–2 paragraphs. Brief context of what was found, the topic, and its relevance. No bullet points.

---

## Key Points
Bullet list of the most important facts, decisions, dates, and findings extracted from the sources.

---

## Stakeholders
Bullet list of people involved: name, role or relationship to the topic, and contact email when available.

---

## Upcoming Meetings
*(omit this section entirely if no calendar search was run)*
List ONLY meetings after the current date related to the topic. Render each using the CALENDAR EVENT DISPLAY FORMAT from the system prompt. Separate with `---`.
If no relevant meetings are found: `No upcoming meetings found for this topic.`

---

## Previous Meetings
*(omit this section entirely if no calendar search was run)*
List past meetings related to the topic. Render each using the CALENDAR EVENT DISPLAY FORMAT from the system prompt. Separate with `---`.
If no relevant meetings are found: `No previous meetings found for this topic.`

---

## Personal Data Resources
Render the hierarchical structure of files found in Phase 2 into a markdown table. Truncate items to a maximum of 10 items per folder. When truncated, append a comment indicating that there are more files not shown.

| Source | Location / Container | Items |
|--------|----------------------|-------|
| Drive | `folder1/` | `file1.txt`, `file2.pdf` |
| Personal Buckets | `my-personal-bucket` | `blob1.csv`, `blob2.json` |
| BigQuery (personal) | `my_dataset` | `table1` – *relation summary* |

---

## Extend Search?
*(ONLY when Final Escalation is reached)*
> "Would you like me to explore any of these files to provide a more detailed response, or is there a specific file you’d like me to examine?"

---

## References
*(mandatory in both modes whenever any data source was used — omit only if the response is based solely on the user's own input with no tool results)*
Include ONLY files, documents, and events from which data was explicitly extracted to produce this response. Never include broad discovery results or unused tool outputs.

| Source | Project Name | Filename | Owner | Created at / Last Update |
|:---:|:---:|:---:|:---:|
| EKB / Drive / Cloud Storage / BigQuery | Human-readable file or event name | Author email or display name | `YYYY-MM-DD` |

- **Source**: exactly one of `EKB`, `Drive`, `Cloud Storage`, or `BigQuery`.
  - **`EKB`**: use for ANY data that originates from the Enterprise Knowledge Base — this includes results from `ekb_semantic_search`, data retrieved from the `documents_chunks` or `documents_metadata` tables, and GCS URIs returned by those results (domain-specific buckets). Never expose the dataset name, table name, or GCS URI in the Source column.
  - **`Drive`**: Google Drive files retrieved via the Drive MCP tools.
  - **`Cloud Storage`**: GCS files read directly from personal or non-EKB buckets (e.g., user-provided buckets in Final Escalation).
  - **`BigQuery`**: results from non-EKB BigQuery tables queried via `execute_query` against user-provided datasets.
- **Project Name**: project name only. NEVER show raw IDs, hashes, or URIs. Example: `Alpha`, `Beta`
- **Filename**: human-readable name only. NEVER show raw IDs, hashes, GCS URIs, dataset names, or table names.
- **Drive entries**: only cite actual files — never include folders (`mime_type = "application/vnd.google-apps.folder"`) as references, even if a folder was used during discovery.
- **Owner**: uploader email, document owner, or event organizer. `Unknown` if unavailable.
- **Created at / Last Update**: `YYYY-MM-DD`. `Unknown` if unavailable.
