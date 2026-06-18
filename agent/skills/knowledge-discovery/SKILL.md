---
name: knowledge-discovery
description: Expert protocol for high-fidelity data retrieval using concurrent Discovery Loops prioritizing Corporate Data over Personal Data.
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

**When the query is clear** (contains at least one concrete subject — a project name, company, person, technology, document title, or specific question), proceed immediately to Discovery Protocol Loops.

---

## Discovery Protocol Loops

**Core Efficiency Rule:** The agent must short-circuit the discovery loops early. If the information requested by the user is fully obtained at the end of *any* iteration, immediately break the iteration process and generate the final report. We only reach all 3 iterations if the data is highly hidden.

### Iteration 1: Massive Parallel Discovery
Launch all baseline data-gathering tools concurrently without waiting.

**1a. Corporate Searches:**
- `ekb_semantic_search`: `query` using the full user prompt.
- `ekb_keyword_search`: `keyword` using primary entities extracted from the prompt.
- `get_current_time`: fetch time bounds for the upcoming Calendar search.

**1b. Personal Data Listings:**
*Keyword Constraint*: When applying filtering parameters to listing tools, use stripped-down keywords of **one or max two words** (e.g., extracting "Alpha" from "Project Alpha").
- `list_files` (Google Drive)
- `search_onedrive` (OneDrive)
- `list_objects` (GCS personal buckets)
- `list_tables` (BigQuery personal datasets)

**Early Exit Check:** If the EKB semantic/keyword chunks found in Iteration 1 completely satisfy the user's request, break the loop and jump straight to **Mandatory Output Structure**.

### Iteration 2: Expanded Anchor & Calendar Sync
If Iteration 1 didn't fully answer the query, synthesize the findings to expand the search.

**2a. Corporate Expansion:**
- Extract larger anchor keywords from Iteration 1's EKB results (e.g., related project codes, linked companies).
- Execute 2-3 additional `ekb_semantic_search` / `ekb_keyword_search` calls using these expanded anchors.
- `list_calendar_events`: Executed now that `get_current_time` has returned the exact dates.

**2b. Personal Data Expansion (Strictly Conditional):**
- *Condition*: This second expansion must ONLY be executed if the first wave of listing tools returned very few files (e.g., 0, 1, 2, or 3 files). If the initial listing found a healthy amount of files, skip this step.
- Execute a second massive concurrent listing (`list_files` / `search_onedrive` / etc.) using the new keywords discovered from the EKB.

**Early Exit Check:** If the newly expanded EKB results + Calendar events now satisfy the request, break the loop and jump straight to **Mandatory Output Structure**.

### Iteration 3: EKB Deep-Read (Strictly Conditional)
**Constraint:** The agent MUST rely on the EKB chunks and metadata as much as possible.
- **Trigger:** IF AND ONLY IF the semantic chunks are still insufficient after Iteration 2, OR the user explicitly asked for the full context of a document.
- **Action:** Select at most **3** EKB GCS files (based on prior context) and call `read_object` on them concurrently.

---

## Personal Data Deep-Dive Protocol

If the user **already requested** in their original prompt to read personal data (e.g., a specific file name or "search my personal files"), jump directly into this Deep-Dive phase alongside Corporate discovery. If they did **not**, do NOT read personal files; wait until they consent via the prompt in the Final Conclusion.

**1. Prioritized Reading Iteration:**
- Using the `file_id` or GCS URIs gathered from the listing tools, read up to **5 files per turn** concurrently across the different sources (`get_file_text` for Drive/OneDrive, `read_object` for GCS, `execute_query` for BigQuery).

**2. Enriched Synthesis:**
- Generate a new response that **combines the previous Corporate summary** (obtained in the first response) and **enriches it** with the new insights discovered in the personal data.

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
Cross-correlate all findings into a unified narrative before writing. You MUST use the exact markdown template below. Do not deviate from these headers. Ensure there are blank lines before and after every header.

```markdown
## Summary
[1–2 paragraphs. Brief context of what was found, the topic, and its relevance. No bullet points.]

## Key Points
- [Bullet list of the most important facts, decisions, dates, and findings extracted from the sources.]

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
| [EKB/Drive/etc] | [Project] | [Filename] | [Email] | [YYYY-MM-DD] |

## Personal Data Resources
*(Omit this entire section if no personal files were listed. Do NOT include the question if the user already authorized reading personal data and we are currently in the Deep-Dive Synthesis.)*

I also found several related files in your personal data sources based on the keywords in your prompt. 

Would you like me to read the content of these files to provide a more robust response? *(Note: This process might take a few minutes to complete.)*

| Source | File / Table Name | Path / Dataset | Owner | Last Updated |
|---|---|---|---|---|
| [Drive/OneDrive/GCS/BQ] | [Filename] | [Path] | [Email] | [Date] |
```

If genuinely no data exists for a section, write `No information found` under that heading — do not skip it. **Exception: the `## Upcoming Meetings` and `## Previous Meetings` sections** — omit both entirely if no calendar search was executed or if calendar searches returned no events relevant to the topic. Do not render these sections with placeholder text in that case.

---

### References Details
*(mandatory in both modes whenever any data source was used — omit only if the response is based solely on the user's own input with no tool results)*
Include ONLY files, documents, and events from which data was explicitly extracted to produce this response. Never include broad discovery results or unused tool outputs.

| Source | Project Name | Filename | Owner | Created at / Last Update |
|:---:|:---:|:---:|:---:|
| EKB / Drive / OneDrive / Cloud Storage / BigQuery | Human-readable file or event name | Author email or display name | `YYYY-MM-DD` |

- **Source**: exactly one of `EKB`, `Drive`, `OneDrive`, `Cloud Storage`, or `BigQuery`.
  - **`EKB`**: use for ANY data that originates from the Enterprise Knowledge Base.
  - **`Drive`**: Google Drive files.
  - **`OneDrive`**: OneDrive files.
  - **`Cloud Storage`**: GCS files read directly from personal or non-EKB buckets.
  - **`BigQuery`**: non-EKB BigQuery tables.
- **Project Name**: project name only. NEVER show raw IDs, hashes, or URIs. Example: `Alpha`, `Beta`
- **Filename**: human-readable name only. NEVER show raw IDs, hashes, GCS URIs, dataset names, or table names.
- **Owner**: uploader email, document owner, or event organizer. `Unknown` if unavailable.
- **Created at / Last Update**: `YYYY-MM-DD`. `Unknown` if unavailable.
