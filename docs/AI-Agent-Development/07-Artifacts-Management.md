# Standalone Observation: Upload Artifact Path from Chat UI to ADK and the Correct Solution Path for Landing-Zone Ingestion

## Purpose

This note documents a standalone technical observation about how a user-uploaded document is expected to travel from the chat UI into the ADK runtime, why the correct initial architectural direction is an upload-style handoff rather than a move-style handoff, why that direction is still incomplete when compared to the current repository implementation, and what solution path best satisfies the landing-zone requirement.

The goal is to answer two questions clearly:

1. What is the most technically correct path for moving a chat-uploaded artifact into the GCS landing zone?
2. Does the current implementation surface already support that path, or is an additional capability required?

---

## Core observation

A chat-uploaded file does **not** begin its lifecycle as a relocatable GCS object. It begins as UI-provided file content that reaches ADK as uploaded message content or an artifact-like payload. Because of that, the correct initial handoff is an **ingestion path** that can take uploaded bytes plus metadata and write a new object into the GCS landing zone.

That makes an upload-oriented design the right first architectural direction.

However, that direction is not complete on its own. The current repository implementation exposes an MCP upload contract that is shaped around either string content or a server-local file path, which is narrower than the needs of a binary chat-upload workflow. As a result, the right architectural direction has been identified, but the current implementation surface does not yet fully realize it.

---

## End-to-end lifecycle being evaluated

The lifecycle under evaluation is the following:

1. A user uploads a document in the Dev Web UI or Gemini Enterprise chat.
2. The uploaded document reaches ADK through the request/message path as file content, not as a pre-existing landing-zone object.
3. The agent or plugin layer must preserve or load that uploaded content in a form that the runtime can use.
4. The system must then create a new object in the GCS landing zone and attach the metadata needed by downstream routing or classification.
5. Downstream data-pipeline logic can then move, classify, or clean up the object according to the repository’s design.

This lifecycle matters because it separates two different storage concerns:

- **initial ingestion of a UI-originated artifact**, and
- **later storage-native relocation of an already-existing object**.

Those are not the same problem and should not be solved by the same primitive unless the architecture already guarantees that the file exists as a stable object in GCS.

---

## Why the upload-oriented path is the correct initial direction

## 1. The file originates in the UI/request plane, not in the storage plane

Public ADK behavior shows that uploaded files are introduced through message parts and artifact-handling logic, not as already-materialized GCS landing-zone objects. ADK Web issue history documents uploads arriving as blob-style parts, and ADK’s artifact/plugin behavior shows that uploaded inline parts can later be persisted as artifacts when explicit saving behavior is enabled.[P1][P2][P6]

That means the system’s first technical responsibility is to **ingest bytes coming from the chat/request path**. A `move_file`-style primitive does not solve that first responsibility because a move operation only makes sense after an addressable storage object already exists.

## 2. The repository’s own design assumes landing-zone creation, not first-hop relocation

The repository design for the enterprise knowledge-base pipeline assumes that the agent receives information, prepares metadata, and writes the uploaded file into the landing zone before downstream classification or routing occurs.[R1]

That design implies object creation in the landing zone, not relocation of an already-existing storage object as the first step.

## 3. A move/copy primitive is naturally a later optimization

A `move_file`, `copy_object`, or `promote_object` capability becomes valuable later, when one or more of the following are true:

- the artifact store is already GCS-backed,
- a canonical `gs://...` object already exists,
- or the architecture wants zero-copy promotion between storage namespaces for performance, cost, or audit reasons.[P3][P4]

That makes upload the correct first-path concept and move/copy the later storage-native optimization.

---

## Why that correct direction is still incomplete in the current repository

The architectural direction is correct, but it is incomplete when compared to the current MCP surface implemented in the repository.

## 1. The MCP upload schema is narrower than the artifact-ingestion problem

The GCS MCP server’s upload request schema accepts `content: Optional[str]` and `local_path: Optional[str]`, along with bucket, object, and metadata fields.[R2]

That is a meaningful limitation for this use case:

- `content` is modeled as string data, not as an explicit binary artifact payload.
- `local_path` assumes the file is available on the **GCS MCP server runtime filesystem**, which is a different boundary from the ADK runtime or chat UI boundary.

So even though “upload, not move” is the correct conceptual direction, the current public tool contract does not yet present a clean binary-safe interface for general document uploads from chat.

## 2. `local_path` is the wrong abstraction for a chat-originated upload

A chat upload does not naturally land on the GCS MCP server’s local filesystem. It first appears in the UI/ADK execution path. The repository’s local development setup also runs separate services for the agent and the GCS MCP server, reinforcing that they do not share the same local file context by default.[R5][R6]

Because of that, `local_path` only works if an extra staging mechanism has already written the file into the GCS MCP server container’s filesystem. That is not the native upload lifecycle being investigated.

## 3. The lower-level GCS client is broader than the exposed MCP contract

The GCS client implementation can create an object from `Union[str, bytes]`, which shows that the lower-level storage layer is already capable of handling raw bytes.[R3]

This is an important distinction:

- the **storage client capability** is broader,
- but the **tool contract exposed to the agent** is narrower.

So the real implementation gap is not that GCS upload is impossible. The gap is that the artifact-to-GCS bridge is not exposed cleanly enough through the current MCP interface.

## 4. The artifact bridge is the actual missing implementation unit

ADK artifact handling is explicit rather than automatic. Public ADK artifact documentation and issue history show that uploaded blobs may remain inline message content unless an artifact-saving path or similar persistence logic is enabled.[P2][P3][P6]

That means the missing end-to-end unit is not simply “call GCS upload.” The missing unit is:

1. receive or load uploaded artifact content from the ADK path,
2. preserve filename, MIME type, and any required metadata,
3. convert that payload into a binary-safe request to the GCS MCP server,
4. write the landing-zone object,
5. and ensure the downstream routing metadata is applied.

That is the real bridge between chat upload and landing-zone storage.

## 5. Metadata handling is part of the ingestion contract

The repository’s design expects landing-zone metadata to support later classification and movement into curated buckets.[R1] The current GCS MCP server supports metadata updates, but the implementation shape is effectively “create object, then patch metadata” rather than a single purpose-built ingestion contract.[R7]

This does not invalidate the current design, but it reinforces that the present upload tool is not yet a complete artifact-ingestion surface.

---

## What this means for the solution path

The solution path should be organized in phases.

## Phase 1: implement a binary-safe artifact-to-GCS ingestion path

The first priority should be a capability that accepts uploaded artifact content from ADK and writes it into the landing zone safely and explicitly.

There are two viable ways to do this.

### Option A: extend the existing upload tool

The current `upload_object` capability can be extended so the MCP schema supports an explicit binary payload representation, such as:

- base64-encoded bytes,
- filename,
- MIME type,
- and metadata.

This is attractive because it reuses the existing tool identity and matches the broader capability already present in the underlying GCS client.[R3]

### Option B: add a dedicated artifact-upload tool

A new tool can be introduced specifically for chat-originated or ADK-originated artifacts, for example:

- `upload_binary_object`,
- `put_artifact_in_landing_zone`,
- or similarly named operation.

This is attractive if the existing upload tool should remain simple for text and local-path use cases while artifact ingestion gets its own explicit contract.

### Phase-1 conclusion

Either approach is better than introducing `move_file` first, because the immediate problem is **ingestion of uploaded artifact content**, not relocation of a storage object that already exists.

---

## Phase 2: make the artifact handoff explicit in the agent workflow

Once the GCS ingestion surface is corrected, the runtime path should be documented and implemented explicitly as:

1. UI upload arrives as ADK-side file content.[P1][P2]
2. The file is persisted or loaded through an explicit artifact-handling path.[P2][P3][P6]
3. The agent or helper layer extracts the bytes and metadata needed for landing-zone placement.[R1]
4. The GCS MCP server receives a binary-safe request and writes the object.[R2][R3]
5. Landing-zone metadata is finalized for downstream routing.[R1][R7]

This phase is essential because the acceptance criterion requires the lifecycle to be documented fully, not only that a storage API exists somewhere in the system.

---

## Phase 3: add storage-native move/copy only if the architecture evolves that way

A `move_file`, `copy_object`, or similar promotion capability should be added later only if the architecture genuinely reaches a point where:

- uploaded artifacts already persist as stable GCS objects,
- those objects expose usable storage references,
- and server-side promotion between GCS locations becomes desirable.

That phase may become valuable, especially if the team wants to avoid downloading and re-uploading large artifacts through the agent runtime.[P4]

But that is a second-stage optimization. It is not the primary answer to the initial chat-upload-to-landing-zone problem.

---

## Final determination

### Determination on the correct path

The technically correct first path is an **upload-style ingestion bridge** from the ADK artifact/message layer into the GCS landing zone.

### Determination on incompleteness

That path is incomplete today because the current MCP upload surface is not yet a clean binary-safe interface for general chat-uploaded documents.

### Determination on whether `move_file` is required first

A new `move_file` implementation is **not** the first required capability for this workflow.

### Determination on the best overall solution

The best overall solution is:

1. **do not treat `move_file` as the primary first fix**,
2. **do not rely on the current `upload_object` contract as fully sufficient**,
3. **first implement a binary-safe artifact-to-GCS upload path**,
4. **then add `move_file` or `copy_object` later only if storage-native promotion becomes a real requirement**.

In practical terms, the correct recommendation is to close the **artifact-ingestion gap** first and the **storage-relocation gap** later.

---

## Citations

### Repository citations

- **[R1]** `docs/Data-Pipelines/Enterprise-Knowledge-Base/Design.md`, lines 13-20, 29-44, 58-69, 78-86.
- **[R2]** `mcp_servers/gcs/app/schemas.py`, lines 91-115.
- **[R3]** `mcp_servers/gcs/app/gcs_client.py`, lines 121-178.
- **[R5]** `Makefile`, lines 44-46.
- **[R6]** `agent/core_agent/README.md`, lines 128-140 and 172-179.
- **[R7]** `mcp_servers/gcs/app/mcp_server.py`, lines 266-312; `mcp_servers/gcs/app/gcs_client.py`, lines 203-234.

### Public citations

- **[P1]** [`google/adk-web`](https://github.com/google/adk-web/issues/41) issue #41, “question: how to capture the filename of the uploaded file via Web UI.”
- **[P2]** [`google/adk-python`](https://github.com/google/adk-python/blob/e967f2812e474476f0e0c71908530ce37ee93928/src/google/adk/plugins/save_files_as_artifacts_plugin.py#L35) source for `SaveFilesAsArtifactsPlugin`, including uploaded inline-data handling and artifact persistence behavior.
- **[P3]** ADK artifact documentation describing artifacts as named, versioned binary data managed by an [`ArtifactService`](https://adk.dev/artifacts/).
- **[P4]** [`google/adk-python`](https://github.com/google/adk-python/issues/5230) issue #5230, documenting that `GcsArtifactService.save_artifact()` raises `NotImplementedError` for `file_data` URI references.
- **[P6]** [`google/adk-python`](https://github.com/google/adk-python/issues/2176) issue #2176, documenting that files uploaded through `adk web` were not saved as artifacts in a runner path where input blobs were not persisted automatically.
