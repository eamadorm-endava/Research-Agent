---
name: meeting-summary
description: create a meeting summary document from a transcript, notes, or meeting file using a fixed template and save the finished .docx to the user's drive. use when the user asks to summarize a meeting file, summarize a transcript from drive, create a meeting summary document, use a meeting-summary template, or save the summary into drive. this skill should be preferred over generic summarization whenever the request includes a meeting file, a named meeting, a template, or document creation.
---

## Mandatory execution mode

This skill must not answer as a generic chat summarizer.

If the request includes any of the following:
- summarize a meeting file
- use a template
- create a document
- save to drive
- summarize a transcript from drive

then do not produce a freeform summary as the main response.

Instead, execute the full workflow:
1. identify the meeting
2. retrieve source evidence
3. extract the 8 required fields
4. generate the .docx from the template
5. save the file to Drive
6. return only the completion report

A paragraph-style meeting summary is not a valid final deliverable for this skill unless the user explicitly asks to see the summary inline in chat.

# Meeting Summary

Create a standardized meeting summary document for one specific meeting and save it into the user's Drive.

## Workflow

1. Identify the target meeting.
2. Gather meeting evidence from MCP Drive Server first.
3. If available, gather extra context for follow-up meetings from related Drive files.
4. Extract the summary fields.
5. Generate the summary document from the template in `assets/meeting-summary-template.md`.
6. Save the file into `AI Meetings Summaries` or the closest equivalent folder in the user's Drive, if folder already exist don't create a new folder with the same name.
7. Report back with the document name, save location, and any missing data.

## 1) Identify the target meeting

Work on one meeting only.

Collect or infer these identifiers from the user's request and available Drive evidence:
- meeting name
- meeting date
- customer, project, or account name
- likely transcript or notes filename

If several meetings could match, choose the best-supported match and say which one you used.

## 2) Retrieve meeting evidence

Use MCP Drive Server as the primary source.

Search Drive for:
- transcript files
- meeting notes
- agendas
- slide decks
- follow-up notes
- action-item docs
- emails or exported notes stored in Drive

Prioritize files whose names or contents match the meeting name and date.

Preferred evidence order:
1. verbatim transcript
2. official meeting notes
3. agenda plus follow-up notes
4. related project docs that clarify context

Capture these fields when available:
- meeting name
- meeting date
- participants
- transcript text or strongest available notes
- future session date
- related documents that would be useful to attach or mention

## 3) Handle follow-up meetings

Treat the meeting as a follow-up when the transcript or filename suggests this is a review, sync, checkpoint, weekly call, status meeting, second session, next session, or continuation.

For follow-up meetings, search Drive for earlier summaries or earlier meeting materials for the same customer, project, or meeting series. Use prior files only to improve context. Do not invent facts that are absent from the current meeting evidence.

## 4) Extract the required summary

Fill these sections in the final document:
- Date of the meeting
- Meeting name
- Main Purpose
- Participants
- Conclusions / Main comments
- Next steps
- Date of the future session
- Documents that could be useful

Extraction rules:
- Derive **Main Purpose** as a short paragraph or 2 to 4 bullets explaining why the meeting happened.
- Summarize **Conclusions / Main comments** as the most important discussion points, decisions, blockers, and notable comments.
- Summarize **Next steps** as action-oriented bullets with owners only when the evidence clearly supports the owner.
- Use `Not found in available sources` for missing required fields.
- Never fabricate participants, dates, decisions, commitments, or owners.
- Keep the summary factual, concise, and grounded in available evidence.
- If the evidence is ambiguous, prefer a cautious summary over a complete-sounding but unsupported one.

## 5) Generate the document from the template

Use the template file in `assets/meeting-summary-template.md`.

Populate the placeholders and preserve this section order:
1. Date of the meeting
2. Meeting name
3. Main Purpose
4. Participants
5. Conclusions / Main comments
6. Next steps
7. Date of the future session
8. Documents that could be useful

## Document generation rule

After extracting the fields, populate the template document with those exact sections and save the document file.

Do not consider the task complete unless:
1. the fields have been mapped to the template placeholders
2. the output document has been created, or a clear storage failure has been reported

## Required output contract

The meeting summary must always be produced using the exact template structure below, in this exact order, with no extra sections and no freeform replacement of the structure:

1. Date of the meeting
2. Meeting name
3. Main Purpose
4. Participants
5. Conclusions / Main comments
6. Next steps
7. Date of the future session
8. Documents that could be useful

Never replace this structure with a narrative paragraph summary.
Never omit a required section.
If a field is unavailable, write exactly: `Not found in available sources`.

## Response modality (critical)

This skill is document-first.

When the user asks for a meeting summary and a document:
- do not return a freeform or inline summary as the main answer
- do not return a narrative paragraph summary
- do not replace the document output with a chat response

Instead:
1. generate the document from the template
2. save the document
3. respond with a completion report only

The summary content must exist inside the generated document, not as a replacement in the chat response.

Only provide the summary inline if the user explicitly asks for it in chat, for example:
- "show me the summary here"
- "paste the summary in the chat"
- "give me the summary text directly"

## Execution completion rule

The task is not complete after extracting or summarizing the meeting.

The task is only complete when:
- the document has been generated from the template
- the document has been saved to Drive, or the save failure has been clearly reported

Do not stop execution after producing a summary.

## Task priority

When both summarization and document creation are requested:
- treat document creation as the primary objective
- treat summarization as an internal step required to populate the document

Do not substitute an inline summary for the document deliverable.

## Document writing rules

- Use clean business language.
- Prefer bullets for conclusions and next steps.
- For participants, use a comma-separated list or bullets depending on what fits the template.
- For useful documents, list Drive file names and, when available, short context for why each file matters.

## Validation before saving

Before saving the document, verify that all 8 required fields are present in the populated template.

If any field is missing, fill it with: `Not found in available sources`.

Do not save or report completion with unresolved placeholders like:
- meeting_name
- date_of_meeting
- any other raw placeholder tokens from the template

## 6) Standardize the output filename and folder

Save the generated file in a Drive folder named `AI Meetings Summaries`.

Folder behavior:
- If `AI Meetings Summaries` exists, use it.
- Otherwise create `AI Meetings Summaries`.
- If creation is blocked, save in the nearest user-approved equivalent and explicitly say so.

Filename format:
`YYYY-MM-DD - meeting-name - Summary.docx`

Filename normalization rules:
- Use the meeting date from the source meeting. If unavailable, use `undated`.
- Replace slashes with hyphens.
- Collapse repeated spaces.
- Keep the human-readable meeting name.
- Remove characters that are invalid for filenames.

## 7) Final response to the user

Always tell the user:
- which meeting you summarized
- what source files were used
- where the summary was saved
- the final document name
- any fields that were missing or inferred

## Final response restriction

Do not include the full meeting summary content in the final response.

The final response must be a completion report only, unless the user explicitly asked to see the summary inline.

The completion report must include:
- meeting identified
- source files used
- document name
- save location
- missing fields
- inferred fields, if any

## Error handling

### No transcript found

If neither Drive nor any available meeting source contains a transcript, do not pretend a transcript exists.

Instead:
- search for notes, agenda, or follow-up files and summarize from those if they are strong enough
- clearly state that no transcript was found
- list what sources were used instead
- if there is not enough evidence for a reliable summary, explain that the summary could not be completed reliably

### Missing participants or future meeting date

Use `Not found in available sources`.

### Missing save folder permissions

Explain that the document could not be stored in the preferred folder and name the fallback location if one was used.

### Multiple possible meetings

If multiple meetings match and one is selected based on strongest evidence, explicitly state which meeting was chosen and why it was selected.

## Transcript guidance for end users

If the user asks why no transcript is available, or if a transcript is missing, tell them:

`To improve future meeting summaries, enable meeting transcription or note-taking during the meeting and make sure the transcript or notes are saved to Drive where the agent can access them.`

## Agent notes

- Prefer Drive evidence over memory.
- Do not summarize multiple meetings into one file unless the user explicitly asks for that.
- Use prior meeting documents only as context, not as a substitute for the current meeting's evidence.
- Keep outputs deterministic and template-based.
- When evidence is incomplete, be explicit about what is missing.
- The template document is the primary deliverable when document creation is requested.

## Final response format

The final response must use exactly this structure:

Meeting summarized: <meeting name>
Sources used: <comma-separated source files>
Document created: <yes/no>
Saved location: <drive folder path>
Filename: <final filename>
Missing fields: <list or "None">
Inferred fields: <list or "None">

Do not include the body of the summary in the final response.
Do not return a narrative recap.
Do not return a prose meeting summary.