# Conversational Context & Memory

ADK manages the lifecycle of a conversation through **Sessions**, **State**, and **Memory**.

## Core Concepts

| Concept | Description |
| :--- | :--- |
| **Session** (`google.adk.sessions.Session`) | A single interaction thread containing the chronological sequence of **Events** (messages, tool calls, agent responses). |
| **State** (`session.state`) | Ephemeral data bound strictly to the current session (e.g., shopping cart items, temporary user preferences). |
| **Memory** | A permanent, searchable knowledge bank spanning *multiple past sessions* and external data. |

## Managing Context: Services

ADK abstracts storage mechanisms via Services so you can swap backends without changing agent logic.

### SessionService

Manages the lifecycle (create, retrieve, update, delete) of `Session` objects. 

| Implementation | Persistence | Use Case | Requirements |
| :--- | :--- | :--- | :--- |
| `InMemorySessionService` | None (Lost on restart) | Local development and testing. | None (Default). |
| `VertexAiSessionService` | Cloud Managed | Production scale. Managed natively by Vertex AI Agent Engine. | GCP Project, Reasoning Engine ID (an Agent already deployed in Agent Engine). |
| `DatabaseSessionService` | Relational DB | Applications requiring self-hosted, persistent storage (e.g., PostgreSQL). | Async DB Driver (e.g., `sqlite+aiosqlite`). |

### MemoryService

Manages the Long-Term Knowledge Store. It ingests information from completed sessions and provides semantic search capabilities so agents can recall past interactions. Like `SessionService`, it supports `InMemory` for dev and `VertexAiMemoryBankService` for production.

---

## Observability & Storage in Production

When using **Vertex AI Agent Engine** (`VertexAiSessionService` and `VertexAiMemoryBankService`), Google Cloud abstracts the underlying database infrastructure:

| Component | Where is it stored? | How to view it? |
| :--- | :--- | :--- |
| **Session & State** | Managed natively within the Vertex AI [Reasoning Engine API](https://cloud.google.com/vertex-ai/docs/reference/rest/v1beta1/projects.locations.reasoningEngines).  | Extracted programmatically using the ADK `SessionService.get(session_id)` layer. |
| **Long-Term Memory** | Secured in a hidden, auto-provisioned Vector Search index managed by Vertex AI [Memory Bank](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/overview). | Queried programmatically via `MemoryService` or using the Google Cloud REST API. |
| **Agent Logs & Traces** | Streamed directly into [Google Cloud Logging](https://console.cloud.google.com/logs). | In the GCP Console, go to **Logs Explorer** and filter by Resource Type: `aiplatform.googleapis.com/ReasoningEngine` or query your specific `resource_id`. |

---
*Reference: [ADK Conversational Context](https://google.github.io/adk-docs/sessions/)*