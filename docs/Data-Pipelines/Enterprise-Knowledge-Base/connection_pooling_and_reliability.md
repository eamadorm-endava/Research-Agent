# Connection Pooling and Pipeline Reliability

## Overview
The Enterprise Knowledge Base (EKB) ingestion pipeline processes documents asynchronously using FastAPI's `BackgroundTasks` deployed on Cloud Run. Under high-concurrency loads (e.g., uploading 10+ files simultaneously), the pipeline experienced intermittent network failures, most notably `SSLEOFError(8, 'EOF occurred in violation of protocol')` when interacting with Google Cloud Storage (GCS) and BigQuery.

This document outlines the root cause of these network failures and details the architectural pattern implemented to guarantee pipeline reliability.

## The Problem: Socket and TLS Exhaustion
Initially, the orchestrator (`KBIngestionPipeline`) and its underlying domain services (`GCSService`, `BQService`, `RAGIngestion`, etc.) were instantiated dynamically for every incoming request. Within the `__init__` method of these services, a new Google Cloud SDK Client was created:

```python
# Anti-pattern: Bypassing Connection Pooling
class BQService:
    def __init__(self):
        self.client = bigquery.Client(project=EKB_CONFIG.PROJECT_ID)
```

### Why this fails under load:
1. **Connection Pool Bypass:** Google Cloud SDKs use the `requests` library (and `urllib3` under the hood) to maintain a thread-safe HTTP connection pool. This pool is tied to the lifecycle of the `Client` object.
2. **TLS Handshake Overhead:** By creating a brand-new `Client` for every uploaded file, the application forced the OS to establish a new TCP connection and perform a full TLS handshake for every single API call.
3. **Socket Starvation:** When multiple background tasks ran concurrently, the rapid creation of un-pooled connections exhausted the available ephemeral ports and triggered rate-limiting/connection drops from the GCP load balancers, resulting in the `SSLEOFError`.

## The Solution: Class Attribute Singletons
To ensure the underlying `urllib3` connection pool is securely shared across all concurrent threads, the architecture was refactored to use a strict **Module-Level Singleton / Class Attribute Pattern**.

```python
# Best Practice: Shared Connection Pooling
from google.cloud import bigquery

# 1. Instantiate the client globally at the module level
bq_client = bigquery.Client(project=EKB_CONFIG.PROJECT_ID)

class BQService:
    # 2. Assign the global client as a Class Attribute
    client = bq_client

    def __init__(self):
        # No client instantiation here
        self.dataset_id = EKB_CONFIG.BQ_DATASET
```

### Why this approach guarantees reliability:
1. **TCP Connection Reuse:** Because the `bq_client` is instantiated at the module level when the app starts, all instances of `BQService` share the exact same memory pointer to the client. This means all concurrent FastAPI background tasks natively share the same TCP connections to GCP, eliminating connection setup latency and socket exhaustion.
2. **Memory Efficiency:** Storing the client as a class attribute rather than an instance attribute saves memory. The client object exists only once in the class definition, rather than being copied into the `__dict__` of every instantiated object.
3. **High Testability:** The class attribute pattern allows for seamless dependency injection and mocking in unit tests (`@patch.object(BQService, 'client')`) without the boilerplate of custom `__init__` assignment.
4. **Pythonic Resolution:** Python's attribute resolution order automatically falls back to class attributes when `self.client` is accessed, meaning the core logic of the class requires zero modification.

## Orchestrator Singleton
To further minimize object allocation overhead, the orchestrator itself (`KBIngestionPipeline`) is instantiated as a module-level singleton in `app/main.py`. The FastAPI router reuses this single, stateless instance to invoke the `run()` method for all incoming documents, ensuring a completely unbottlenecked, highly concurrent ingestion workflow.
