---
name: knowledge-discovery
description: Expert protocol for high-fidelity data retrieval across Corporate and Personal data sources. Triggered on ANY request to find, search, investigate, or summarize information, whether broad or narrow.
---

## Pre-Search Validation
Before proceeding, verify whether the user has clearly stated the target of the search.
**A query is considered unclear when it:**
- Expresses intent without a topic (e.g., "search the EKB", "conduct research", "look it up").
- Names only a source, not a subject (e.g., "check the knowledge base", "query the EKB", "search SharePoint").
- Is too vague to form a meaningful search (e.g., "find documents", "search for info").

**When the query is unclear**, execution must halt. Do not guess, infer, or proceed with a search. Respond EXACTLY with:
> "What topic, document, project, or information would you like me to search for?"

## Phase 0: Pre-Search Keyword Extraction
Before launching any search tools, internally analyze the user's prompt to distill the core subjects.
- Extract the primary entities (e.g., project names, company names, specific technologies).
- Strip these down into **pure keywords of maximum 1 or 2 words** (e.g., extracting "Alpha" from "Project Alpha status report").
- These distilled keywords MUST be used for all keyword-based corporate searches in Phase 1 to ensure high recall. NEVER use the raw, conversational user query for keyword parameters.

## Phase 1: Massive Parallel Corporate Discovery

**CRITICAL RULE:** Do NOT launch personal data tools in this step unless the user explicitly declared them in their prompt. Corporate data MUST be searched first.
**OMNI-SEARCH PROTOCOL:** If the user explicitly asks to search "all sources", "everywhere", or "all data" (e.g. "en todas las fuentes posibles"), you MUST bypass the sequential flow. You must launch **both Corporate (Phase 1) and Personal (Phase 4) listing/search tools concurrently** in the very first turn.

Execute exactly 6 corporate tools CONCURRENTLY in a single parallel turn:
1. `ekb_semantic_search`: `query` using the specific core request extracted from the user's prompt (e.g., "Alpha project status" rather than "Hello, can you tell me about the Alpha project status?"). Do NOT use the raw conversational prompt.
2. `ekb_keyword_search`: `keyword` using the distilled 1-2 word entities from Phase 0.
3. `search_jira_issues`: JQL mapping to the distilled 1-2 word entities.
4. `search_confluence_pages`: CQL expression mapping to the distilled 1-2 word entities.
5. `search_sharepoint_sites`: broad business keyword (1-2 words max) from Phase 0.
6. `list_calendar_events`: call with `date_min` and `date_max` empty to default to 6 months of bounds. Use `sort_order` = `asc`.

## Phase 2: Strict Relevance Filtering
Evaluate the returned corporate data. If a source returns a keyword match that is semantically irrelevant to the user's prompt, you MUST completely ignore it to avoid distractions. NEVER include irrelevant matches in the final response or the references table.

## Phase 3: Corporate Response & Mandatory UX Flow
Generate the response based ONLY on the relevant corporate data.
**CRITICAL REQUIREMENT:** At the end of the response, you MUST:
1. Explicitly list which corporate sources were used to generate the answer.
2. Conditionally ask the user the exact prompt below. **DO NOT ask this if:** you are just responding to conversational chat (e.g., "thanks"), you did not perform a search, or you already searched personal data sources.
> "This information was obtained from corporate data sources. Would you like me to also search in your personal data sources (Google Drive, OneDrive, Cloud Storage buckets, and BigQuery tables)? It might take a few minutes."

## Phase 4: Personal Source Expansion
ONLY if the user replies "Yes" (or explicitly requested it upfront), execute the personal data source tools.

**Anchor Extraction (Context Graph)**:
Before searching personal data, build a relational map from the merged corporate results to generate enriched keywords. Do NOT just send the raw user query.
- **Identities**: issue keys, confluence page names, sharepoint site/page ids, summaries.
- **Context**: description/body texts — key for generating personal data listing keywords.
- **Entities**: company names (clients/partners), technologies, technical stacks.
- **Relational Mapping**: map project names to their associated companies and tech stacks. Use these mapped pairs as the primary enriched keywords for the personal data listing tools.
- **People**: uploader_email, reporter, assignee, and stakeholders mentioned in summaries.

Use these enriched, mapped keywords (1 to 2 words max) to execute the personal data source tools concurrently.

## Phase 5: Deep Content Extraction (Universal)
Whether you are extracting context from personal data (Phase 4) or the user is asking to deep dive into a corporate result (Phase 3), you MUST execute the respective deep-read tools (`get_file_text`, `read_file`, `get_sharepoint_site_page`, `read_confluence_page`, `get_jira_issue_details`, etc.) on the top hits to extract the full body text and generate an enriched, in-depth summary. Do not stop at just listing titles.

### EKB vs. Personal Data Definitions
The current Google Cloud project ID is `<project_id>`. Use this logic to distinguish EKB vs Personal sources:
- **Corporate EKB Buckets**: Any GCS bucket starting with `<project_id>-kb-` (e.g., `<project_id>-kb-finance`, `<project_id>-kb-hr`, `<project_id>-kb-it`).
  - **CRITICAL RESTRICTION**: NEVER search in infrastructural buckets like `<project_id>-kb-landing-zone` or `<project_id>-kb-rag-staging`. Only target domain-specific buckets.
- **Corporate EKB Datasets**: The `knowledge_base` BigQuery dataset.
- **Personal Sources**: Google Drive, Microsoft OneDrive, and ANY BigQuery table or Cloud Storage bucket that does NOT match the EKB patterns above.

---

## Data Source Tool Gotchas (MUST READ)

### UNIVERSAL READING LIMITS
- **Max Concurrency Per Turn**: You may execute a MAXIMUM of **5 deep-read tools concurrently** in a single turn.
- **Dynamic Max Per Source**: 
  - **Multi-Source (Omni-Search)**: If you are reading from multiple data sources in the same loop, you may read a maximum of **2 files per data source**.
  - **Single-Source**: If you are doing a deep dive into only a **single data source** (e.g., only Confluence, or only SharePoint), you may use your full concurrency limit to read up to **5 files from that single source**.
- **Max Loop Limit**: You are allowed to iterate up to a maximum of **8 internal reading loops**.

### EKB DEEP DIVE PREFERENCE
- For EKB data (vectorized in BQ), you MUST prefer using `ekb_semantic_search` to obtain more targeted information.
- ONLY use `read_object` to read the full GCS file from a domain bucket if the absolute full context of the entire document is needed, or if the user explicitly requires full reading to be accurate and precise.

### SHAREPOINT
- **Sequence**: 1. `search_sharepoint_sites`, 2. `discover_sharepoint_site_content`, 3. `list_sharepoint_site_drives` / `list_sharepoint_site_lists` / `list_sharepoint_site_pages`, 4. `get_sharepoint_site_page` / `ingest_sharepoint_drive_item`.
- Never invent IDs; use IDs returned by prior SharePoint tool calls. Do not expose raw IDs in the final answer.

### GOOGLE DRIVE
- `list_files(file_name=<keyword>)` — returns list of files. Strip keywords to max two words, but **single-word keywords are heavily preferred** for maximum discovery.
- `get_file_text(file_id=<id>)` — extracts text using a real `file_id`.

### MICROSOFT ONEDRIVE
- `find_items(query=<keyword>)` — searches OneDrive.
- `read_file(file_id=<id>)` — extracts text using a real `file_id`.

### CALENDAR
- The response schema includes `server_current_time_utc`. Use this along with the events' timezones to accurately classify events as `Past` or `Future` relative to the server time.
- Display Format: render each event as a bullet-point block (Title, Time, Attendees, Meet link, Attachments, Description) separated by `---`.

### BIGQUERY
1. `list_tables` to confirm which tables exist.
2. `get_table_schema` if column names can't be inferred.
3. `execute_query` with validated SQL.

### JIRA & CONFLUENCE
- **Jira**: `search_jira_issues` followed by `get_jira_issue_details` if needed.
- **Confluence**: `search_confluence_pages` followed by `read_confluence_page` if needed. Returns `inject_file_data: True`.

### GCS FILE READING
- If reading a file directly from GCS, parse the GCS URI into `bucket_name` and `object_name`, and call `read_object`. The system intercepts it and loads it natively.

---

## Output Format (Full Report Mode)
When synthesizing information from multiple sources, structure your final response using the exact markdown template below. **Do NOT include the "Output Format" title in your response.**

### Formatting Rules
1. **STRICT NO-MONOLOGUE RULE:** You MUST NOT output conversational filler, internal thoughts, or intermediate status updates (e.g., "I have searched X", "I am now reading Y"). Your final response must strictly start with `## Summary`.
2. **Meeting Sections:** Omit the "Upcoming Meetings" and "Previous Meetings" sections entirely if no calendar search was executed or if no events exist in those timeframes.
3. **Reference Table Source Names:** Only use `BigQuery` or `Cloud Storage` for Personal Sources in the References table. EKB buckets and `knowledge_base` datasets must be attributed as `EKB`.
4. **Personal Search Follow-Up Prompt:** If you retrieved data from corporate sources AND you have NOT yet searched personal data, you must display the following question (outside of the Reference table)
"This information was obtained from corporate data sources. Would you like me to also search in your personal data sources (Google Drive, OneDrive, Cloud Storage buckets, and BigQuery tables)? It might take a few minutes."

### Output Template
```markdown
## Summary
[1–2 paragraphs. Brief context of what was found across the systems, the core topic, and its relevance. No bullet points.]

## Key Findings
- [Bullet list of the most important facts, decisions, ticket updates, page entries, and dates extracted from the sources.]

## Stakeholders
- [Name (Role) - Email]

## Upcoming Meetings
[List meetings occurring after the current server time. Separate with `---`]

## Previous Meetings
[List meetings that occurred before the current server time. Separate with `---`]

## References
| Source | Project Name | Filename / Item Name | Owner / Assignee | Created at / Last Update |
|:---:|:---:|:---:|:---:|:---:|
| [EKB/Drive/OneDrive/SharePoint/etc] | [Project] | [Filename] | [Email] | [YYYY-MM-DD] |

```
