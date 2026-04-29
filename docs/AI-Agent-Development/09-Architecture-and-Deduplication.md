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

### The Challenge
In Gemini Enterprise, multi-modal files uploaded to the chat are re-transmitted by the platform on **every turn**. This is done to ensure the LLM always has the full context of the files.
*   **Default Behavior**: A standard saving plugin would see these re-transmitted files and save them to GCS as new versions for every single message.
*   **Consequence**: Excessive GCS storage costs and a cluttered session history.

### The Solution: DeduplicatingArtifactPlugin
The `DeduplicatingArtifactPlugin` (located in `internal_tools/artifacts/plugin.py`) inherits from the base saving logic but adds a state-aware verification layer.

#### Implementation Logic:
1.  **Key Listing**: Before processing a message, it lists all existing artifact keys for the current session.
2.  **Identity Verification**: It compares incoming file display names against the stored keys.
3.  **Conditional Save**: 
    *   If the file is already present, it retrieves the `latest_version` and skips the GCS write.
    *   If the file is new, it performs a standard `save_artifact` call.
4.  **Content Sanitization**: It strips the binary `inline_data` from the message parts and replaces it with a lightweight reference: `[Uploaded Artifact: "filename"]`.

---

## 4. Local Development Parity

While the code is unified, the local runner (`adk web`) often requires explicit CLI configuration to match Cloud behavior.

- **Storage**: Forced via `--artifact_service_uri gs://$(ARTIFACT_BUCKET)` in the `Makefile`.
- **Bucket Resolution**: The `Makefile` and `GCPConfig` (via `AliasChoices`) both handle the mapping between `.env` names (like `ARTIFACT_STAGING_BUCKET`) and the application's required `ARTIFACT_BUCKET` field.
