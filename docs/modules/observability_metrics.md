# Module Documentation - Observability & Cloud Monitoring Metrics

This module provides native OpenTelemetry metrics, distributed tracing, and structured logging export to **Google Cloud Monitoring**, **Google Cloud Trace**, and **Google Cloud Logging** for the ADK-based AI Agent.

---

## 1. Architecture & Design Principles

1. **Native ADK Telemetry Integration**:
   - Rather than rolling custom exporters or disconnected SDK initialization, telemetry utilizes `google.adk.telemetry.google_cloud.get_gcp_exporters(enable_cloud_metrics=True, enable_cloud_tracing=True)` and `google.adk.telemetry.setup.maybe_set_otel_providers()`.
   - The OpenTelemetry `MeterProvider` is registered with a `PeriodicExportingMetricReader` wrapping Google Cloud's `CloudMonitoringMetricsExporter`.
2. **Lifecycle Plugin Instrumentation**:
   - Metrics collection hooks cleanly into Google ADK's `BasePlugin` lifecycle (`ObservabilityPlugin`):
     - `before_run_callback` / `after_run_callback`: Measures total turn latency and tracks request counts.
     - `before_model_callback` / `after_model_callback` / `on_model_error_callback`: Intercepts LLM generation, records prompt/output token counts from `usage_metadata`, and measures generation duration.
     - `before_tool_callback` / `after_tool_callback` / `on_tool_error_callback`: Measures execution latency for individual tool calls and records tool error rates.
3. **Cardinality Protection**:
   - High-cardinality values (`session_id`, `user_id`) are restricted to Traces and Logs.
   - Cloud Monitoring metrics only retain bounded, low-cardinality attributes (`gen_ai.agent.name`, `gen_ai.tool.name`, `gen_ai.request.model`, `gen_ai.token.type`, `error.type`), preventing metric quota exhaustion and runaway costs.
4. **Fail-Safe Telemetry**:
   - Every callback in `ObservabilityPlugin` is wrapped in defensive guard clauses and error logging. If Cloud Monitoring or OpenTelemetry experiences network blips or outages, agent execution continues uninterrupted.

---

## 2. Directory Structure

```text
agent/core_agent/
├── observability.py                           # Central entry point: initializes Cloud Logging & Cloud Monitoring
├── plugins/
│   └── observability_plugin/
│       ├── __init__.py                        # Plugin package export
│       ├── metrics.py                         # OpenTelemetry Meter & metric counter definitions
│       └── plugin.py                          # ADK BasePlugin implementation capturing lifecycle metrics
└── tests/
    └── test_observability.py                  # Pytest unit tests for setup and plugin lifecycle
```

---

## 3. Metric Schema & Instruments

All instruments adhere to the official [Google ADK Metrics Schema](https://adk.dev/observability/metrics/#metrics-schema) and OpenTelemetry GenAI Semantic Conventions:

| Metric Name | Type | Unit | Monitored Attributes (Dimensions) | Description |
|---|---|---|---|---|
| `gen_ai.client.token.usage` | Histogram | `tokens` | `gen_ai.agent.name`, `gen_ai.token.type` (`input` / `output`), `gen_ai.request.model`, `gen_ai.response.model` | Number of tokens consumed per model call |
| `gen_ai.client.operation.duration` | Histogram | `s` | `gen_ai.agent.name`, `gen_ai.operation.name`, `gen_ai.request.model`, `error.type` | Latency of the model generation call |
| `gen_ai.agent.invocation.duration` | Histogram | `s` | `gen_ai.agent.name`, `error.type` | Total duration of an agent turn |
| `gen_ai.agent.invocation.requests` | Counter | `{request}` | `gen_ai.agent.name` | Total count of agent turns initiated |
| `gen_ai.agent.invocation.errors` | Counter | `{error}` | `gen_ai.agent.name`, `error.type` | Total count of failed model invocations |
| `gen_ai.tool.execution.duration` | Histogram | `s` | `gen_ai.tool.name`, `gen_ai.agent.name`, `error.type` | Latency of tool execution |
| `gen_ai.tool.execution.requests` | Counter | `{call}` | `gen_ai.tool.name`, `gen_ai.agent.name` | Total count of tool invocations |
| `gen_ai.tool.execution.errors` | Counter | `{error}` | `gen_ai.tool.name`, `gen_ai.agent.name`, `error.type` | Total count of tool execution failures |

---

## 4. Usage & Initialization

### Initialization
Observability is automatically initialized when importing `agent.core_agent`:

```python
from agent.core_agent.observability import setup_observability

# Automatically called in agent/core_agent/__init__.py:
setup_observability()
```

### Agent Configuration
The `ObservabilityPlugin` is registered with the root agent during construction:

```python
from agent.core_agent.plugins import ObservabilityPlugin

root_agent = Agent(
    name="osiris-coordinator",
    plugins=[
        ObservabilityPlugin(),
        # other plugins...
    ],
    ...
)
```

---

## 5. Verification & Testing

Run unit tests via `uv`:
```bash
uv run pytest agent/tests/test_observability.py
```

To verify metrics interactively in Jupyter, execute:
`notebooks/observability/metrics_verification.ipynb`.
