# File Ingestion Wrapper

This tool wrapper specifically intercepts the output of tools (such as MCP Servers) that return GCS URIs meant for multimodal context injection.

When a tool returns a response indicating `_inject_file_data = True`, this wrapper dynamically appends a `types.Part(file_data=...)` directly into the active session's event history. This enables the "zero-copy" ingestion strategy, avoiding LLM roundtrips and latency.

## Architecture Nuances

Because this wrapper encapsulates the entire `BaseToolset` (often `McpToolset` instances), it acts as a proxy for the ADK framework. To avoid breaking core ADK functionalities, it delegates specific methods to the underlying original toolset:

### OAuth and `get_auth_config`
The ADK framework natively looks for an `AuthConfig` in the outermost toolset to trigger the OAuth exchange for credentials. If the `FileIngestionToolsetWrapper` hides the original `McpToolset`, the framework won't find the auth configuration, leading to `401 Unauthorized` and `403 Forbidden` errors on remote Cloud Run MCP servers.
**Solution**: We explicitly override `get_auth_config` to delegate and return `self.original_toolset.get_auth_config()`.

### `close`
MCP servers frequently maintain active HTTP connections or child processes that must be explicitly terminated to avoid resource leaks.
**Solution**: We override the `close` method to await `self.original_toolset.close()`, guaranteeing that all underlying resources are cleanly released when the runner shuts down.

### `process_llm_request`
Some toolsets require observing the outgoing LLM request to inject context, append tokens, or log activity. If the wrapper doesn't forward this, the original toolset loses visibility.
**Solution**: We override `process_llm_request` and forward the arguments to the original toolset.

### Dynamic Naming with `__new__`
ADK logging and runner shutdown routines print the toolset class name. To prevent all toolsets from genericly appearing as `FileIngestionToolsetWrapper` in logs, we override `__new__` to dynamically construct a subclass that inherits the name of the original toolset (e.g., `McpToolset`).
