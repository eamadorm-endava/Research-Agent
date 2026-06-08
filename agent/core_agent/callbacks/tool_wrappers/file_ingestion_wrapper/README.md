# File Ingestion Wrapper

This tool wrapper specifically intercepts the output of tools (such as MCP Servers) that return GCS URIs meant for multimodal context injection.

When a tool returns a response indicating `_inject_file_data = True`, this wrapper dynamically appends a `types.Part(file_data=...)` directly into the active session's event history. This enables the "zero-copy" ingestion strategy.
