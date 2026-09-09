# ADK Plugins

Plugins provide a powerful way to bundle multi-hook logic, tools, and state management into a single modular component.

## Plugins vs. Callbacks
- A **Callback** is typically a single function targeting one specific lifecycle hook (e.g., `before_agent`).
- A **Plugin** is a class that can hook into multiple lifecycle events simultaneously, register its own tools, and maintain internal state across hooks. 

## Plugin Lifecycle Hooks
Plugins have access to all the standard ADK callbacks (`before_agent`, `after_model`, etc.), but they also expose specialized messaging hooks:
- **`on_user_message`**: Triggers when a new user message arrives but before it is processed.
- **`on_model_message`**: Triggers when the model is generating a message.

## When to use a Plugin
Use a plugin when you need cohesive, reusable logic that spans multiple hooks, such as intercepting user attachments (`on_user_message`) and later validating the model's response (`after_model`) within the same domain.

---

## Registered Custom Plugins

The Research-Agent project utilizes four custom plugins located in this package:

| Plugin | Directory | Primary Purpose |
|---|---|---|
| **ContinuationPlugin** | [`continuation/`](continuation/README.md) | Catches empty LLM payloads (silent failures) caused by context saturation and prompts user with a continuation message. |
| **GeminiEnterpriseFileIngestionPlugin** | [`gemini_enterprise_ingestion/`](gemini_enterprise_ingestion/README.md) | Resolves user uploads from the Gemini Enterprise chat interface by replacing UI text tags with hydrated GCS `types.Part(file_data=...)` references. |
| **MultimodalFileInjectionPlugin** | [`multimodal_file_injection/`](multimodal_file_injection/README.md) | Injects GCS multimodal files (PDFs, images) downloaded by MCP servers directly into the model request as siblings to tool execution responses. |
| **ObservabilityPlugin** | [`observability_plugin/`](observability_plugin/README.md) | Manages end-to-end telemetry across turns: contextual logging (Loguru), distributed trace span enrichment, and OpenTelemetry GenAI metrics emission to Cloud Monitoring. |
