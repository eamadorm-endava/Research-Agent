# Thread-Safe Token Management

## The Challenge: Race Conditions in Authentication
In high-concurrency environments like Cloud Run, multiple agent instances or parallel tool calls can attempt to retrieve an authentication token (ID Token or OAuth Token) simultaneously. 

Without proper synchronization, this leads to several issues:
1. **Redundant API Calls**: Multiple threads triggering the Google Metadata Server or ADC refresh concurrently, wasting resources and potentially hitting rate limits.
2. **Cache Inconsistency**: One thread might overwrite a valid cached token with an older one or an error result.
3. **Stale Tokens**: Failure to handle the narrow window between token expiration and a fresh retrieval.

## The Solution: Synchronized Global Cache

To resolve these race conditions, the `auth.py` module implements a thread-safe caching architecture:

### 1. Centralized Lock Mechanism
We use a `threading.Lock()` to gate access to the global `_ID_TOKEN_CACHE`. This ensures that:
- Only one thread can check and refresh the cache at a time.
- The "Check-then-Act" pattern is atomic.

### 2. Dual-Path Retrieval with Fallback
The `get_id_token` function follows a strict hierarchy to ensure availability:
- **Path 1: Metadata Server**: The primary path for production (GCP). It decodes the JWT to extract the real expiry time and caches it with a safety buffer.
- **Path 2: Local ADC**: The fallback path for development environments. It uses a shorter TTL (60s) to accommodate local environment rotations.

### 3. Deterministic Testing (Clearing the State)
Because the cache is global and persistent within the process life cycle, unit tests could suffer from "false positives" (tests passing because they hit the cache instead of exercising the retrieval logic). 
We implemented `clear_id_token_cache()` specifically for the testing suite to reset the security state before each test case.

## Implementation Details
- **Location**: `agent/core_agent/security/auth.py`
- **Synchronization**: `_CACHE_LOCK` (threading.Lock)
- **Persistence**: `_ID_TOKEN_CACHE` (dict)

```python
# snippet of the thread-safe check
with _CACHE_LOCK:
    if audience in _ID_TOKEN_CACHE:
        token, expiry = _ID_TOKEN_CACHE[audience]
        if expiry > now + 30: # 30s buffer for reliability
            return token
```
