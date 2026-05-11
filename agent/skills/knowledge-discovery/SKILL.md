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
→ Cast a wide net across all sources. Synthesize across EKB, Calendar, BQ, and Drive.

---

## Targeted Mode Protocol

### Wave 1 — Broad Semantic Discovery
Call `ekb_semantic_search` with the following parameters only:
- `project_id`: `"ag-core-dev-fdx7"` *(always)*
- `query`: user's keywords or document name — strip intent words (`"give me"`, `"what is"`, `"duration"`, `"status"`, `"date"`, `"summary"`)
- `top_k`: `15`

Do NOT include `filename`, `domain`, `project_filter`, or `trust_level` in Wave 1.

From every result, extract and store: `filename`, `gcs_uri`, `chunk_data`, `document_summary`, `domain`.

**If Wave 1 returns zero results:** skip Wave 2 and GCS Long Context. Proceed immediately to the Calendar Search Protocol + Drive Search Protocol running in parallel.

### Wave 2 — Per-File Focused Search (only if Wave 1 returned results)
Select the top 3 most relevant files from Wave 1, ranked by ascending cosine distance. For each, launch one `ekb_semantic_search` call. Run all simultaneously:
- `project_id`: `"ag-core-dev-fdx7"` *(always)*
- `query`: the user's actual information need — what they want to know, not the filename
- `filename`: exact verbatim value from the `filename` field of a Wave 1 result — never paraphrase or rewrite
- `top_k`: `30`

Run the **CALENDAR SEARCH PROTOCOL** (from the system prompt) in parallel with Wave 2, starting both immediately after Wave 1 completes. Calendar runs regardless of Wave 1 outcome.

**Hard Rules:**
- Run all Wave 2 calls simultaneously.
- `filename` MUST come verbatim from a prior `ekb_semantic_search` result `filename` field in this session. Never use user's phrasing.
- `top_k` must be `30` in Wave 2 to maximize chunk coverage per file.

### GCS Long Context (only if Wave 1 + Wave 2 chunks are insufficient)
Trigger ONLY when both waves returned results but the specific data was NOT found within the returned chunks. Do NOT trigger if Wave 1 returned zero results — go to Drive Search instead.

For the top 3 files used in Wave 2, run all steps in parallel (following the **GCS FILE READING RULE** from the system prompt):
1. Parse each `gcs_uri` → `bucket_name` (everything between `gs://` and the first `/`) and `object_name` (everything after that first `/`).
2. Call `read_object(bucket_name=<bucket_name>, object_name=<object_name>)` to retrieve `mime_type`.
3. Call `import_gcs_to_artifact(gcs_uri=<gcs_uri>, mime_type=<mime_type from step 2>)`.

After all 3 imports complete, call `load_artifacts` once.

### Drive Search (Targeted Mode)
Trigger when Wave 1 returned zero EKB results, OR when GCS Long Context did not yield the answer.
Follow the **DRIVE SEARCH PROTOCOL** defined in the system prompt using keywords extracted from the user's query.

---

## Discovery Mode Protocol

### Phase 1: Contextual Anchoring (The Hook)
1. **Semantic Search**: Call `ekb_semantic_search` with the following parameters only:
   - `project_id`: `"ag-core-dev-fdx7"` *(always)*
   - `query`: user's natural language question
   - `top_k`: `10`

   Never add `filename`, `domain`, `project_filter`, or `trust_level` in Phase 1.

2. **Anchor Extraction**: Build a "Context Graph" from the results:
   - **Identities**: `filename`, `gcs_uri`, `document_summary`.
   - **Context**: `document_summary` / `description` — key for generating Phase 2 Drive keywords.
   - **Entities**: company names (clients/partners), technologies, technical stacks.
   - **Relational Mapping**: map project names to their associated companies and tech stacks — use these as primary anchors for Phase 2 Drive and Calendar searches.
   - **People**: `uploader_email` and stakeholders mentioned in summaries.
   - **Locations**: `gcs_uri` values (for GCS deep-dive in Phase 3 Level 1).

3. **Expansion**: If results are narrow, broaden using extracted entities before moving to Phase 2.
   - **Zero-Result Fallback**: If `ekb_semantic_search` returns no results, extract keywords directly from the user's original prompt (company names, project names, technologies, dates, people) and use those as Phase 2 anchors. Skip Phase 2b (no BQ project context to anchor against).

### Phase 2: Parallel Context Acquisition (Broad Search)
Launch all the following simultaneously. *Efficiency Rule: never repeat the same tool call with the same parameters in the same session.*

**2a. Calendar** — Follow the **CALENDAR SEARCH PROTOCOL** defined in the system prompt exactly.

**2b. BigQuery (Structural Context)** — Follow the **BIGQUERY QUERY PROTOCOL** defined in the system prompt. Target the `documents_metadata` table inside the `knowledge_base` dataset. Retrieve metadata (summaries, domain, project associations) linked to the entities identified in Phase 1. Skip if Phase 1 returned zero EKB results. Include always the filter: where latest = true. So it always get the last version of the document.

**2c. Google Drive** — Follow the **DRIVE SEARCH PROTOCOL** defined in the system prompt (Stage 0 through Wave 2 only). Do NOT execute Stage 4 file reading in Phase 2 — file reading is deferred to Phase 3 Level 3.

### Phase 3: Synthesis & Targeted Deep Dive (Escalation Path)

**Level 1: EKB Deep-Dive (GCS)**
For the top 3 high-relevance `gcs_uri` values from Phase 1, run in parallel (following the **GCS FILE READING RULE** from the system prompt):
1. Parse each `gcs_uri` → `bucket_name` (everything between `gs://` and the first `/`) and `object_name` (everything after).
2. `read_object(bucket_name=<bucket_name>, object_name=<object_name>)` → get `mime_type`.
3. `import_gcs_to_artifact(gcs_uri=<gcs_uri>, mime_type=<mime_type>)`.

After all imports complete, call `load_artifacts` once.

**Level 2: Calendar Deep-Dive (Personal Context)**
From relevant events found in Phase 2a, apply the Selective Attachment Reading rule (from the **CALENDAR SEARCH PROTOCOL** in the system prompt): call `get_file_text(file_id=<EventAttachment.file_id>)` only when `EventAttachment.title` or `CalendarEvent.description` contains a term directly relevant to the query.

**Level 3: Drive Iterative Discovery**
Execute Stage 4 of the **DRIVE SEARCH PROTOCOL** (Prioritized File Reading) against the candidate pool built in Phase 2c: High-triage files first, then Medium. At most 5 `get_file_text` calls per turn, all in parallel. If answer not found, extract new keywords from text and run one additional Wave 1 cycle. Maximum 1 extra cycle.

**Level 4: Relationship Fallback (Implicit Mapping)**
Analyze EKB metadata (descriptions, summaries, tech stacks) for shared technologies, industry themes, or generalities. Use these broader themes to re-evaluate Phase 2 results for high-fidelity implicit relationships.

**Level 5: Final Conclusion**
Produce the standard output. Write `No information found` under any section where data is missing. The `## Extend Search?` section from **Final Escalation** below MUST appear — omitting it when Level 5 is reached means the task is incomplete.

---

## Cross-Mode Fallback

**Targeted → Discovery Fallback:**
If Targeted Mode has exhausted all steps without finding the answer, continue with Discovery Mode's unique steps — skipping any tool calls already made:
- Run Phase 2b BQ `documents_metadata` query if not already executed.
- Re-run Drive search with full keyword decomposition if the entity map differs meaningfully from keywords already used. Do not repeat identical `list_files` calls.
- Do NOT repeat `ekb_semantic_search`, `get_current_time`, or `list_calendar_events` calls already made.

**Discovery → Targeted Fallback:**
If Discovery Mode has exhausted all phases (Phase 1 through Level 4) without finding the answer, run Targeted Mode's unique steps — skipping any tool calls already made:
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
Cross-correlate all findings into a unified narrative before writing. Follow this exact section order. If genuinely no data exists for a section, write `No information found` under that heading — do not skip it.

**Summary** *(always present)*
1–2 paragraphs. Brief context of what was found, the topic, and its relevance. No bullet points.

---

**## Key Points**
Bullet list of the most important facts, decisions, dates, and findings extracted from the sources.

---

**## Stakeholders**
Bullet list of people involved: name, role or relationship to the topic, and contact email when available.

---

**## Upcoming Meetings**
List ONLY meetings after the current date related to the topic. Render each using the CALENDAR EVENT DISPLAY FORMAT from the system prompt. Separate with `---`.
If none: `No upcoming meetings found for this topic.`

---

**## Previous Meetings**
List past meetings related to the topic. Render each using the CALENDAR EVENT DISPLAY FORMAT from the system prompt. Separate with `---`.
If none: `No recent meetings found for this topic.`

---

**## Extend Search?** *(ONLY when Final Escalation is reached)*
Include the escalation message verbatim from the **Final Escalation** section above.

---

**## References** *(mandatory in both modes whenever any data source was used — omit only if the response is based solely on the user's own input with no tool results)*
Include ONLY files, documents, and events from which data was explicitly extracted to produce this response. Never include broad discovery results or unused tool outputs.

| Source | Filename | Owner | Created at / Last Update |
|:---:|:---:|:---:|:---:|
| EKB / Drive / Cloud Storage / BigQuery | Human-readable file or event name | Author email or display name | `YYYY-MM-DD` |

- **Source**: exactly one of `EKB`, `Drive`, `Cloud Storage`, or `BigQuery`.
  - **`EKB`**: use for ANY data that originates from the Enterprise Knowledge Base — this includes results from `ekb_semantic_search`, data retrieved from the `documents_chunks` or `documents_metadata` tables, and GCS URIs returned by those results (domain-specific buckets). Never expose the dataset name, table name, or GCS URI in the Source column.
  - **`Drive`**: Google Drive files retrieved via the Drive MCP tools.
  - **`Cloud Storage`**: GCS files read directly from personal or non-EKB buckets (e.g., user-provided buckets in Final Escalation).
  - **`BigQuery`**: results from non-EKB BigQuery tables queried via `execute_query` against user-provided datasets.
- **Filename**: human-readable name only. NEVER show raw IDs, hashes, GCS URIs, dataset names, or table names.
- **Drive entries**: only cite actual files — never include folders (`mime_type = "application/vnd.google-apps.folder"`) as references, even if a folder was used during discovery.
- **Owner**: uploader email, document owner, or event organizer. `Unknown` if unavailable.
- **Created at / Last Update**: `YYYY-MM-DD`. `Unknown` if unavailable.
