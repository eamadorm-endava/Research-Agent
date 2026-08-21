# Observability in Research-Agent

Observability is a critical pillar for any production-grade AI system. For the Research-Agent, we utilize a native Google Cloud approach to provide a comprehensive view into the agent's behavior, performance, and cost. This is achieved by combining three fundamental pillars of observability: **Logging, Monitoring, and Tracing**.

By leveraging OpenTelemetry (OTEL) and Google Cloud Operations suite (formerly Stackdriver), we can capture deep, multimodal interactions out of the box.

---

## 1. Tracing

### What is it?
Tracing tracks the progression of a single user request as it traverses through the various components, plugins, tools, and foundation models of the AI Agent. A "Trace" represents the entire journey, while "Spans" represent the individual operations (like a specific API call to Gemini, or a tool execution).

### Why is it required?
AI Agents orchestrate complex, non-deterministic workflows. When a user asks a question, the agent might invoke multiple tools, search knowledge bases, and make several LLM calls. Tracing allows developers to:
- Pinpoint exactly where latency is introduced.
- Visualize the exact chain of thought and execution path.
- Inspect the raw prompts and responses sent to and from the LLM, including multimodal payloads (like images or extracted text).

### How it improves observability
By using the OpenTelemetry auto-instrumentation injected via our `ObservabilityPlugin`, every agent turn is tagged with a `session_id` and `user_id`. This allows us to filter traces in **Cloud Trace** per user or session, making it incredibly easy to debug specific interactions or audit the behavior of the agent in complex scenarios.

**References:**
- [Finding and Viewing Generative AI Events in Cloud Trace](https://docs.cloud.google.com/trace/docs/finding-traces#view_generative_ai_events)
- [Collect and View Multimodal Prompts and Responses](https://docs.cloud.google.com/stackdriver/docs/instrumentation/collect-view-multimodal-prompts-responses?hl=en)

---

## 2. Logging

### What is it?
Logging is the process of recording discrete events that happen during the execution of the agent. This includes system events, errors, warnings, and informational messages (like "Agent Turn started for Session ID: X").

### Why is it required?
While traces show *how* a request flowed, logs provide the *context* around specific events. They are essential for:
- Capturing application crashes or unhandled exceptions.
- Auditing user access and security events.
- Debugging specific plugin or tool failures that might not be fully captured by an LLM span.

### How it improves observability
In the Research-Agent, we use `loguru` bridged directly to `google.cloud.logging` (configured in `agent/core_agent/observability.py`). This ensures that logs are not just dumped as flat text to standard output, but are sent as structured payloads to **Cloud Logging** with their correct severity levels (INFO, WARNING, ERROR). Because the `ObservabilityPlugin` binds the `session_id` and `user_id` to the logger, every log entry is automatically enriched with user context.

**References:**
- [AI Agent Platform: Logging](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/logging)

---

## 3. Monitoring (Metrics)

### What is it?
Monitoring involves capturing aggregated, quantitative data over time. Metrics provide a high-level view of the system's health, performance, and utilization.

### Why is it required?
Metrics answer questions like "How many tokens are we consuming per hour?", "What is the average latency of our agent?", or "How many users are interacting with the system right now?". They are required for:
- Setting up alerts and Service Level Objectives (SLOs).
- Monitoring infrastructure scaling.
- Tracking token consumption for cost analysis.

### What metrics are obtained?
By utilizing the native Google Cloud AI Agent observability integration and OpenTelemetry, the agent automatically surfaces critical metrics to **Cloud Monitoring**, including:
- **Token Usage**: Number of input, output, and total tokens consumed per request.
- **Latency**: Duration of LLM calls, tool executions, and overall agent turns.
- **Error Rates**: Tracking failed LLM generation requests or tool errors.
- **Invocation Counts**: The total volume of requests handled by the agent.

### How it improves observability
With metrics flowing into Cloud Monitoring, we can build unified dashboards that track the financial cost (via tokens) and the performance (via latency) of the Research-Agent over time. This completely replaces the need for custom, manual BigQuery insertions.

> [!NOTE]
> **Metrics vs Traces/Logs for Session Grouping**
> Standard time-series metrics in Cloud Monitoring are usually aggregated at the application or model level to prevent "high cardinality" issues (i.e., avoiding millions of unique time-series from highly unique `session_id`s). 
> 
> However, because our `ObservabilityPlugin` injects `session_id` into every **Log** and **Trace span**, you can still easily group and analyze latency or token usage *per session* by using **Cloud Trace Analytics** or by creating **Log-based Metrics** in GCP.

**References:**
- [AI Agent Platform: Monitoring](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/monitoring)
- [Instrumenting AI Agents with ADK](https://docs.cloud.google.com/stackdriver/docs/instrumentation/ai-agent-adk?hl=en)
- [ADK Metrics Schema](https://adk.dev/observability/metrics/#metrics-schema)

---

## Additional Reading

To understand the broader landscape of AI observability and the underlying enterprise architecture, refer to:
- [Google Cloud Gen AI Agent Observability Overview](https://docs.cloud.google.com/stackdriver/docs/instrumentation/ai-agent-overview?hl=en)
- [Scaling the Gemini Enterprise Agent Platform](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale)
- [OpenTelemetry for AI Agent Observability](https://opentelemetry.io/blog/2025/ai-agent-observability/)
