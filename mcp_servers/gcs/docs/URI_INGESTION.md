# URI-Based GCS Ingestion Pattern

This document describes the high-performance ingestion pattern for the GCS MCP server and the AI Agent.

## Overview

To optimize multi-modal analysis (PDFs, Images, Videos), the Research-Agent project has transitioned from a **Binary-Download** model to a **URI-Reference** model. 

### Legacy Model (Binary)
1. Agent calls `read_object`.
2. MCP Server downloads blob and returns bytes.
3. Agent sends bytes (Base64) to LLM.
4. **Impact**: High memory usage, high latency, double-hop bandwidth.

### Current Model (URI Reference)
1. Agent calls `read_object` (MCP).
2. MCP Server fetches **metadata only** (MIME type, size, URI) and returns it.
3. Agent registers a session artifact using the **GCS URI** and **MIME type**.
4. Agent sends a `file_data` reference to Gemini.
5. Gemini reads the file directly from GCS.
6. **Impact**: Zero memory footprint on the agent, **zero dependencies on `google-cloud-storage` in the agent**, sub-second tool calls.

## Data Structures

### GcsObjectMetadata
The `read_object` tool returns a strictly typed metadata model:
- `mime_type`: Content type (e.g., `application/pdf`).
- `size_bytes`: Raw size.
- `creation_date`: YYYY-MM-DD.
- `creation_time`: HH:MM:SS.
- `custom_metadata`: User-defined key-value pairs.

## Tooling

### read_object (MCP)
- **Input**: `bucket_name`, `object_name`.
- **Output**: `gcs_uri`, `metadata` (Nested Pydantic Model).

### import_gcs_to_artifact (Agent)
- **Input**: `gcs_uri`.
- **Output**: Registers the URI in the ADK session context.
