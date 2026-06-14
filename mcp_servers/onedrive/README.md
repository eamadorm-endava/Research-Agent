# OneDrive MCP Server

This directory contains the Model Context Protocol (MCP) server for integrating Microsoft OneDrive with the AI Agent.

## Architectural Constraints & Nuances

Several critical architectural constraints were established to guarantee secure, highly performant, and LLM-friendly execution. When modifying this component, the following nuances must be strictly respected:

### 1. In-Memory Pagination Caching & Cloud Run Lifecycle
Microsoft's Graph API relies heavily on opaque `@odata.nextLink` tokens for pagination. 
- **What it is and how it works:** When a folder or search result contains too many items to fit in a single response (e.g., >200 items), the Graph API returns the first batch along with an `@odata.nextLink` property containing a full URL for the next page. To retrieve the subsequent items, the client must make a new request to this exact URL, which contains complex, encoded `$skipToken` states.
- **Why LLMs struggle to manage it:** LLMs are excellent at reasoning but poor at blindly passing around long, volatile strings across multiple conversation turns. If an LLM is asked to fetch "the second page" of results, it naturally attempts to pass a simple integer parameter (e.g., `page=2`). Forcing the LLM to store, recall, and correctly replay a 300-character, URL-encoded skip token inevitably leads to hallucinations, truncated strings, or broken API calls.

To solve this, the client uses a Python-side caching and slicing strategy. It hides the `nextLink` complexity entirely from the LLM, allowing the agent to simply pass a human-readable `page=1, 2, 3` argument, and the client handles fetching and slicing the items internally.
- **Class-Level State:** Because `FastMCP` treats every tool call as a separate stateless request, the cache is stored at the **class level** (`OneDriveClient._cache`) so that it persists across subsequent tool calls within the same server memory space.
- **Token Segregation & Secret Handling:** To enable federated searches securely, the cache key natively incorporates a hash of the user's `access_token` (`cache_key = (endpoints, hash(access_token))`). This guarantees that User A can never accidentally hit User B's cache. Furthermore, the raw token is strictly typed via `pydantic.SecretStr` in the client, ensuring the token is never inadvertently logged or dumped into memory traces in its raw form.
- **Cloud Run Viability:** Cloud Run spins down idle instances, which wipes the in-memory cache. However, Cloud Run instances remain warm for roughly 15 minutes by default. Because the cache TTL is exactly **10 minutes**, the cache perfectly covers active, back-to-back LLM conversation bursts while expiring naturally before Cloud Run destroys the instance.

### 2. Custom Python-Side Filtering
The Graph API `search` endpoint does not natively support strict OData `$filter` queries for creation dates or modified dates.
- **Download First, Filter Later**: The client downloads *all* files within the requested scope (following all `nextLink` pagination pages) into a massive list, which is then cached.
- **In-Memory Filtering & Pagination**: To enforce mathematical accuracy (`min_creation_date <= item <= max_creation_date` AND/OR `min_last_modified_date <= item <= max_last_modified_date`), all custom filtering is applied *after* retrieving the payload from the cache. The remaining items are then sorted and sliced (`[start:end]`) to return the exact requested page. This guarantees complex multi-variable filters work reliably without hammering the API.
- **The Two-Pronged Discovery Strategy**:
  - `find_items`: A fuzzy, global "first discovery" search tool. It uses tokenized substring matching (split by spaces, hyphens, and underscores) against both the `name` AND `folder_path`. This guarantees that querying `item_name="Alpha"` returns files named "Alpha" *and nested children* inside a folder named "Alpha".
  - `list_folder_contents`: An exact, deterministic traversal tool. It retrieves a deterministic, flat list of the exact files and subfolders strictly inside a specific parent folder, bypassing the search engine entirely.

> [!CAUTION]
> **CRITICAL BEHAVIORAL DIFFERENCE**: 
> - **`find_items`**: Uses a global fuzzy search. It searches recursively, but it **ONLY** returns items that explicitly match the search query. It will not return the full physical contents of a folder unless every single item matches the query.
> - **`list_folder_contents`**: Uses the physical `/children` directory listing. It is not recursive, but it guarantees an exact physical snapshot of the immediate folder contents, bypassing any search filters or delays.

- **Graph API Search Limitations (Prefix-Only)**: The Microsoft Graph API `/search` used by `find_items` is strictly prefix-based. If a user is looking for a folder named "TestingLargerFolder", searching for "testing" will match, but searching for "larger" will return 0 results because Microsoft does not support mid-word substring searches in its index.
- **Agent Override**: Agents can explicitly pass `use_cache=False` to force a cache reload if they expect a file was just uploaded.

### 3. Pydantic Constraints (Hallucination Prevention)
The `schemas.py` file dictates the exact contract between the LLM and the backend.
- `MainFolder`: Agents interact with friendly concepts (`MY_FILES`, `SHARED_WITH_ME`) which are mapped to Graph API endpoints under the hood via the `MainFolder.get_endpoint()` StrEnum.
- Dates: Date filters (e.g., `min_creation_date`, `max_last_modified_date`) use strict regex constraints (`YYYY-MM-DD`). An inherited `@model_validator` guarantees that if any minimum date boundary is provided, its corresponding maximum boundary MUST also be provided, ensuring strict windowing.

### 4. GCS Landing Zone & Zero-Copy Streaming
The `read_file` method must **never** return raw file content to the LLM due to memory constraints and context window limits.
- The payload is streamed in a "zero-copy" fashion directly into the centralized `GCS Landing Zone`.
- **Filename Preservation**: The original filename returned from the Graph API must be respected exactly as-is. It must not be cleaned, sanitized, or altered (do not remove spaces, dashes, or special characters).
- **Dynamic Authorization**: After the stream is uploaded to GCS, the MCP Server mathematically isolates the file by injecting an IAM condition (`resource.name.startsWith("projects/_/buckets/{LANDING_ZONE_BUCKET}/objects/{app_name}/{user_id}/")`) into the bucket's IAM policy.
  - The condition MUST use the exact title `"uploader-folder-access"`.
  - The role granted MUST be `roles/storage.objectAdmin` at the specific `app_name/user_id/` folder level.
- The method automatically extracts the file's absolute path from the Graph API (`parentReference.path`), strips the opaque `/drive/root:` prefixes, and returns the explicit `file_path`, `gcs_uri`, and `inject_file_data: True` to trigger the backend's Multimodal injection pipeline seamlessly.

### 5. Recursive Tree Synthesis
Graph API search endpoints natively return a completely flattened list of items. To provide LLMs with a comprehensible layout, the client implements a highly optimized, O(N) recursive tree synthesis algorithm (`_build_recursive_tree`):
- **Path Normalization & Dynamic Rooting:** The client aggressively normalizes inconsistent SharePoint pathing (like `//`) and dynamically finds the deepest common denominator path among all fetched items. This becomes the "virtual root", preventing the LLM from processing hundreds of irrelevant upstream folders.
- **Set-Optimized Folder Synthesis:** If a file belongs to a parent directory that was *not* explicitly returned by the API search, the algorithm automatically synthesizes a "virtual" parent folder using its `folder_path`. It utilizes a pre-computed Python `set` of unique paths to ensure this synthesis strictly executes once per directory, eliminating O(N*M) recursion overhead on massive folders.

## Required Scopes

To use this client and the Microsoft Graph API, the delegated access token must contain the following scopes from Microsoft Entra ID:
- `offline_access`
- `Files.Read.All`
- `Sites.Read.All`
- `User.Read` (implied for profile)

## Usage Example

```python
from pydantic import SecretStr
from app.onedrive_client import OneDriveClient
from app.config import MainFolder
from app.schemas import FindItemsRequest, ReadFileRequest, SessionContext

# Initialize the client securely using SecretStr
client = OneDriveClient(access_token=SecretStr("mock-token"))

# Request paginated search results with custom Python-side filters
request = FindItemsRequest(
    main_folder=MainFolder.MY_FILES,
    item_name="budget"
)
results = client.find_items(request)

# Read and ingest a file to the GCS Landing Zone
read_req = ReadFileRequest(
    file_id="12345", 
    dependencies=SessionContext(
        app_name="agent-engine", 
        user_id="user@example.com", 
        session_id="session-1"
    )
)
response = client.read_file(read_req)

print(response.gcs_uri)
``` 
