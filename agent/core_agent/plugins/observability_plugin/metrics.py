from opentelemetry import metrics
from google.adk import version as adk_version

# OpenTelemetry Meter instance for ADK GenAI operations
meter = metrics.get_meter(
    name="gcp.vertex.agent",
    version=adk_version.__version__,
)

# Operational counters matching the ADK metrics schema
agent_invocation_requests = meter.create_counter(
    "gen_ai.agent.invocation.requests",
    unit="{request}",
    description="Total count of agent invocations.",
)

agent_invocation_errors = meter.create_counter(
    "gen_ai.agent.invocation.errors",
    unit="{error}",
    description="Total count of agent invocation errors.",
)

tool_execution_requests = meter.create_counter(
    "gen_ai.tool.execution.requests",
    unit="{call}",
    description="Total count of tool executions.",
)

tool_execution_errors = meter.create_counter(
    "gen_ai.tool.execution.errors",
    unit="{error}",
    description="Total count of tool execution errors.",
)
