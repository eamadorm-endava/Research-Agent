# 09 - App Architecture and Deduplication

This document describes the structural refinements made to the Research-Agent to ensure production stability, strict type safety, and optimized handling of recursive artifact uploads in Gemini Enterprise.

## 1. Unified App Construction Pattern

To maintain absolute parity between Local Development and Production, the application utilizes a "Base-to-Wrapper" construction pattern in the `AppBuilder`.

### The Strategy
1.  **Construct Base App**: The builder first creates a standard `google.adk.apps.app.App`. This instance contains all the "business logic" (Agent, Toolsets, Plugins).
2.  **Evaluate Environment**:
    *   **Local**: Returns the base `App` directly. Storage and tracing are managed via external CLI flags in the `Makefile`.
    *   **Production**: Wraps the base `App` into a `vertexai.agent_engines.AdkApp`. This adds the production-grade `GcsArtifactService` and enables tracing features.

This approach guarantees that if a plugin or tool works locally, it will behave identically in production because the underlying `App` object is shared.

---

## 2. Type Safety and Fluent API

The builder package (`agent/core_agent/builder/`) implements strict Python typing standards to improve maintainability and prevent runtime errors.

- **Explicit Unions**: Replaced `|` with `Union` from the `typing` module for return types.
- **Lowercase Built-ins**: Standardized on `list[]` instead of `List[]`.
- **No `Any`**: Replaced all `Any` occurrences with specific types or `BasePlugin` / `BaseAgent` base classes.
- **Fluent Interface**: Chaining methods like `.with_plugins()` or `.with_skills()` ensures a declarative and readable configuration flow.

---

## 3. Recursive Artifact Prevention

### The Challenge: Functional Overlap
In Gemini Enterprise, multi-modal files uploaded to the chat are re-transmitted by the platform on **every turn**. This is done to ensure the LLM always has the full context of the files.

Research reveals a significant **functional overlap** between the Gemini Enterprise UI and the ADK's programmatic storage logic:
1.  **Platform Ingestion**: When a user submits a file via the chat interface, Gemini Enterprise handles the initial ingestion internally, creating a reference (Version 0) within the system's managed storage.
2.  **Plugin Redundancy**: If a standard `SaveFilesAsArtifactsPlugin` is enabled, it intercepts the message and attempts to save it again. Because the ADK artifact service is version-sensitive, it perceives this as a second save, immediately creating **Version 1** after the UI's **Version 0**.
3.  **The Paradox**: Removing the plugin entirely in production (a common recommendation) solves the redundancy but can break local development workflows or custom tools that expect a unified artifact interface. Furthermore, keeping binary data inline to satisfy the UI's rendering requirements leads to token exhaustion.

### The Solution: DeduplicatingArtifactPlugin
The `DeduplicatingArtifactPlugin` (located in `plugins/artifacts/plugin.py`) resolves this overlap by introducing a state-aware verification layer that works across both local and production environments.

#### Implementation Logic:
1.  **Key Listing**: Before processing a message, it lists all existing artifact keys (filenames/hashes) for the current session.
2.  **Identity Verification**: It compares incoming file display names or content-based hashes (SHA-256) against the stored keys.
3.  **Conditional Save**: 
    *   **If the file is already present** (e.g., saved by Gemini Enterprise UI as Version 0): It retrieves the `latest_version` and skips the redundant GCS write.
    *   **If the file is new**: It performs a standard `save_artifact` call.
4.  **Content Sanitization**: It strips the binary `inline_data` from the message parts and replaces it with a lightweight reference: `[Uploaded Artifact: "filename"]`. This prevents token bloat while keeping the UI's grounding reference intact.
5.  **Deterministic Naming**: For files lacking a `display_name` (common in some UI paths), it generates a stable filename from the content hash, ensuring consistency across turns.

---

## 4. Local Development Parity

While the code is unified, the local runner (`adk web`) often requires explicit CLI configuration to match Cloud behavior.

- **Storage**: Forced via `--artifact_service_uri gs://$(ARTIFACT_BUCKET)` in the `Makefile`.
- **Bucket Resolution**: The `Makefile` and `GCPConfig` (via `AliasChoices`) both handle the mapping between `.env` names (like `ARTIFACT_STAGING_BUCKET`) and the application's required `ARTIFACT_BUCKET` field.
