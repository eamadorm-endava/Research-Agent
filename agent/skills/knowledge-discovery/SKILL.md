---
name: knowledge-discovery
description: Expert protocol for high-fidelity data retrieval using concurrent Corporate Searches (EKB, Jira, Confluence, SharePoint, Calendar) and sequenced Personal Data discovery.
---

## Pre-Search Validation

Before proceeding, verify whether the user has clearly stated the target of the search.

**A query is considered unclear when it:**
- Expresses intent without a topic (e.g., "search the EKB", "conduct research", "look it up", "find something")
- Names only a source, not a subject (e.g., "check the knowledge base", "query the EKB", "search SharePoint", "look into Jira")
- Is too vague to form a meaningful search (e.g., "find documents", "search for info")

**When the query is unclear**, execution must halt and the following prompt shall be presented:
> "What topic, document, project, or information would you like me to search for?"

Do not guess, infer, or proceed with a search. Wait for the user's answer before continuing.

**When the query is clear** (contains at least one concrete subject — a project name, company, person, technology, document title, ticket identifier, or specific question), proceed immediately to the Discovery Protocol Loops.

## Follow-Up Execution Protocol

When a follow-up question is asked, first check if the context obtained from previous searches already contains the specific, detailed answer. If the answer is clearly present, respond from context. 

If the answer is NOT already present, or if the follow-up introduces a new topic not related to the previous prompt, you MUST initiate a completely new Discovery Loop targeting the new information gap. This means executing the 5 concurrent corporate discovery queries again. Do NOT answer "Information is unavailable" without executing a new search across corporate or permitted sources.

Furthermore, if the follow-up question is broad, the exact opt-in prompt regarding personal or authorized data sources MUST be appended at the end of the response (see Mandatory Output Structure).

**Handling the Opt-In ("Yes"):**
If the user replies "Yes" to the personal data opt-in prompt, this constitutes a follow-up that requires an active search. Because the prompt might just be "Yes", keywords MUST be synthesized from the *original* query and a "Context Graph" built from the prior corporate findings (EKB, Calendar, Jira, Confluence, SharePoint).

**Anchor Extraction (Context Graph)**:
Build a relational map from the merged corporate results before searching personal data:
- **Identities**: filename, gcs_uri, issue keys, confluence page names, sharepoint site/page ids, summaries.
- **Context**: description/body texts — key for generating personal data listing keywords.
- **Entities**: company names (clients/partners), technologies, technical stacks.
- **Relational Mapping**: map project names to their associated companies and tech stacks — use these as the primary enriched keywords for the personal data listing tools.
- **People**: uploader_email, reporter, assignee, and stakeholders mentioned in summaries.

Immediately execute all tools in **1c. Personal Data Listings** (`list_files`, `find_items`, `list_objects`, `list_tables`) CONCURRENTLY (in parallel, within the exact same agent step) using these enriched keywords derived from the Context Graph. Do NOT skip them or run them sequentially. Once the files are listed, proceed to the **Personal Data Deep-Dive Protocol** to read the most relevant files.

---

## Discovery Protocol Loops

**Core Efficiency Rule:** The discovery loops must be short-circuited early. If the required information is fully obtained at the end of *any* iteration, the iteration process must be immediately broken, and the final report generated. All 3 iterations are reached only if the data is highly hidden.

### Iteration 1: Massive Parallel Discovery
Launch all baseline corporate data-gathering tools concurrently without waiting.

**1a. Corporate Searches (EKB, SharePoint, Calendar, Confluence, Jira):**
**MANDATORY RULE:** You MUST trigger all 5 of the following corporate discovery queries simultaneously across the explicitly defined corporate data sources to gather contextual assets. DO NOT skip any of these 5 sources unless explicitly told to exclude them by the user. DO NOT run any personal data list tools until these have executed.
- `ekb_semantic_search`: `query` using the full user prompt.
- `ekb_keyword_search`: `keyword` using primary entities extracted from the prompt.
- `search_jira_issues`: pass a clean text summary keyword or project constraint JQL mapping to the extracted entity (e.g., `summary ~ "keyword"` or `text ~ "keyword"`).
- `search_confluence_pages`: pass a CQL expression mapping to the core subject token (e.g., `text ~ "keyword"`).
- `search_sharepoint_sites`: pass a broad business keyword or primary entity extracted from the prompt.
- `get_current_time`: fetch time bounds for the Calendar search.

**1b. Mandatory Calendar Sync:**
- Immediately after `get_current_time` returns the exact dates, `list_calendar_events` MUST be executed using those bounds. This step is mandatory in Iteration 1 and must be completed before any Early Exit check is evaluated. Calendar is a critical Corporate Data source.

**1c. Personal / Authorized Source Listings (ONLY IF explicitly requested):**
*Constraint*: For broad questions, skip these tools entirely to preserve rapid response times, UNLESS the user explicitly asked to search personal files or authorized shared repositories in the prompt.
*Keyword Constraint*: The keywords used for `list_files`, `find_items`, `list_objects`, and `list_tables` must strictly and exclusively map to the core subject/entity explicitly asked about (e.g., the specific project name, company name, or technical topic). 
- Use stripped-down keywords of **one or max two words** (e.g., extracting 'Alpha' from 'Project Alpha').
- NEVER use intent words (summary, report, find, status).
- NEVER list files using keywords unrelated to the exact current request.
- ALL listing tools below MUST be executed CONCURRENTLY in the same parallel tool-call step. Do not execute them sequentially.
  - `list_files` (Google Drive)
  - `find_items` (OneDrive)
  - `list_objects` (GCS personal buckets)
  - `list_tables` (BigQuery personal datasets)

**Early Exit Check:** If the corporate results found in Iteration 1 completely satisfy the request, break the loop and proceed straight to **Mandatory Output Structure**.

### Iteration 2: Expanded Anchor & Calendar Sync
If Iteration 1 did not fully answer the query, synthesize the findings to expand the search scope.

**2a. Corporate Expansion:**
- Extract larger anchor keywords from Iteration 1's EKB, Jira, Confluence, SharePoint, and Calendar results (e.g., related project codes, linked companies, Jira components, Confluence spaces, SharePoint site IDs).
- Execute additional concurrent `ekb_semantic_search` / `ekb_keyword_search` / `search_jira_issues` / `search_confluence_pages` / `discover_sharepoint_site_content` / `search_sharepoint_drive_items` calls using these expanded anchors.

**2b. Personal Data Expansion (Strictly Conditional):**
- *Condition*: This second expansion must ONLY be executed if the first wave of listing tools was launched AND returned very few files (e.g., 0, 1, 2, or 3 files). If the initial listing was deferred (broad question) or found a healthy amount of files, skip this step.
- Execute a second massive concurrent listing (`list_files` / `find_items` / `list_objects` / `list_tables`) using the new keywords discovered from the corporate context.

**Early Exit Check:** If the newly expanded corporate results and Calendar events now satisfy the request, break the loop and proceed straight to **Mandatory Output Structure**.

### Iteration 3: Corporate Deep-Read (Strictly Conditional)
**Constraint:** The metadata and summaries from Iteration 1 & 2 MUST be relied upon as much as possible.
- **Trigger:** IF AND ONLY IF the chunks/metadata are still insufficient after Iteration 2, OR the full context of a document/ticket/page was explicitly requested.
- **Action:** Select at most **3** corporate items (based on prior context) and call `read_object` (for EKB GCS), `read_confluence_page` (for Confluence), `get_jira_issue_details` (for Jira), `get_sharepoint_site_page`, or `ingest_sharepoint_drive_item` (for SharePoint) concurrently.
---

## Personal Data Deep-Dive Protocol

If the reading of personal or authorized shared data was **already requested** in the original prompt (e.g., a specific file name, or "search my personal files"), jump directly into this Deep-Dive phase alongside Corporate discovery. If it was **not** requested, do NOT read personal files; wait until consent is provided via the prompt in the Final Conclusion.

**1. Sequenced Discovery and Reading (Up to 8 Loops):**
To ensure a comprehensive but safe discovery, you MUST follow this strict multi-phase sequence when executing the Deep-Dive:

- **Phase 1 (Iteration 1) — First Broad Listing:** - Execute the listing tools (`list_files`, `find_items`, `list_objects`, `list_tables`) across ALL authorized data sources concurrently, using the primary keywords.
  - **Constraint:** Maximum of **2 list/search requests** per authorized data source in this step. Do NOT read any files/items yet.

- **Phase 1.5 (Iteration 1.5) — First Folder Expansion (Conditional):**
  - If Phase 1 uncovered any relevant **Folders**, execute a listing tool specifically targeting those folders' contents.
  - **Constraint:** Maximum of **2 list/search requests** per authorized data source. Do NOT read any files/items yet. Skip this phase if no folders were found.

- **Phase 2 (Iteration 2) — Second Broad Listing:**
  - Execute a second wave of listing tools across ALL authorized data sources concurrently, exactly like Phase 1, but using **different or expanded keywords**.
  - **Constraint:** Maximum of **2 list/search requests** per authorized data source. Do NOT read any files/items yet.

- **Phase 2.5 (Iteration 2.5) — Second Folder Expansion (Conditional):**
  - If Phase 2 uncovered NEW relevant **Folders**, execute a listing tool specifically targeting those new folders' contents.
  - **Constraint:** Maximum of **2 list/search requests** per authorized data source. Do NOT read any files/items yet. Skip this phase if no new folders were found.

- **Phase 3 (Iteration 3) — First Targeted Reading:**
  - Analyze the combined metadata from all previous listing phases. Select the most promising files and read them concurrently.
  - **Constraint:** Maximum of **2 files/items read** per turn PER authorized data source (e.g., 2 from Drive, 2 from OneDrive, 2 from GCS).

- **Phase 4+ (Iterations 4 to 8) — Iterative Deep-Dive:**
  - Evaluate the data found. If the necessary information is not yet complete, select the next batch of most promising files based on filenames or folder context, and read them.
  - **Folder Rule:** If any iteration uncovers a relevant new Folder, you MUST include a listing tool specifically targeting that folder's contents in the very next step, while still respecting the 2 list requests per source limit.
  - Repeat this analysis and targeted reading loop until the required information is found, up to the maximum limit of 8 total iterations.

**2. Enriched Synthesis:**
- Generate a new response that **combines the previous Corporate summary** (obtained in the first response from EKB, Jira, and Confluence) and **enriches it** with the new insights discovered in the personal data.

---

## Mandatory Output Structure

Before writing the response, classify the question:
- **Concise Mode**: clear, narrow answer (a single fact, name, date, count, status, issue state, or yes/no).
- **Full Report Mode**: answer requires synthesizing across multiple corporate records, documents, issues, or time periods.

---

#### Concise Mode
Respond directly in plain prose (1–3 sentences). Always append the `## References` table when any data source was used — never omit it. Skip all other sections.

---

#### Full Report Mode
Cross-correlate all findings into a unified narrative before writing. The exact markdown template below MUST be used. Do not deviate from these headers. Ensure there are blank lines before and after every header.

```markdown
## Summary
[1–2 paragraphs. Brief context of what was found across corporate systems and files, the topic, and its relevance. No bullet points.]

## Key Points
- [Bullet list of the most important facts, decisions, ticket updates, page entries, dates, and findings extracted from the sources.]

## Stakeholders
- [Name (Role) - email]

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

## References
| Source | Project Name | Filename | Owner | Created at / Last Update |
|:---:|:---:|:---:|:---:|:---:|
| [EKB/Jira/Confluence/Drive/OneDrive/SharePoint/etc] | [Project] | [Filename / Title] | [Email / Assignee] | [YYYY-MM-DD] |

## Personal / Authorized Data Resources
**CRITICAL REQUIREMENT:** You MUST append this section and exact prompt at the very bottom of your response IF personal files or authorized shared repositories were NOT searched in Iteration 1 (e.g. because it was a broad question). 
*(Omit this entire section ONLY IF reading personal or authorized shared data was already authorized and the Deep-Dive Synthesis is currently active, or if personal files or authorized shared repositories were already searched).*

> "This information was obtained from the corporate data sources, do you want me to also search in your personal or authorized data sources: OneDrive, Google Drive, Cloud Storage buckets or in BigQuery tables you have access to? It might take a few minutes."
```

If genuinely no data exists for a section, write `No information found` under that heading — do not skip it. **Exception: the `## Upcoming Meetings` and `## Previous Meetings` sections** — omit both entirely if no calendar search was executed or if calendar searches returned no events relevant to the topic. Do not render these sections with placeholder text in that case.

---

### References Details
*(mandatory in both modes whenever any data source was used — omit only if the response is based solely on user input with no tool results)*

| Source | Project Name | Filename / Item Name | Owner / Assignee | Created at / Last Update |
|:---:|:---:|:---:|:---:|:---:|
| EKB / Drive / OneDrive / SharePoint / Cloud Storage / BigQuery / Jira / Confluence | Human-readable name | Author email or display name | `YYYY-MM-DD` |

- **Source**: exactly one of `EKB`, `Google Drive`, `OneDrive`, `SharePoint`, `Cloud Storage`, `BigQuery`, `Jira`, or `Confluence`.
  - **`EKB`**: use for ANY data that originates from the Enterprise Knowledge Base, including ANY data from the `knowledge_base` BigQuery dataset.
  - **`Drive`**: Google Drive files.
  - **`OneDrive`**: OneDrive files.
  - **`SharePoint`**: SharePoint site pages, list items, document-library files, or files ingested from SharePoint for reading.
  - **`Cloud Storage`**: GCS files read directly from personal or non-EKB buckets.
  - **`BigQuery`**: personal or non-EKB BigQuery tables. Do NOT use this for tables in the `knowledge_base` dataset; those belong to `EKB`.
- **Project Name**: project name only. NEVER show raw IDs, hashes, or URIs. Example: `Alpha`, `Beta`
- **Filename**: human-readable name only. NEVER show raw IDs, hashes, GCS URIs, dataset names, or table names.
- **Owner**: uploader email, document owner, or event organizer. `Unknown` if unavailable.
- **Created at / Last Update**: `YYYY-MM-DD`. `Unknown` if unavailable.
