from typing import Any
from loguru import logger
from opentelemetry.trace import get_current_span
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.agents.invocation_context import InvocationContext


class ObservabilityPlugin(BasePlugin):
    """
    A plugin to inject session and user context into OpenTelemetry traces
    and Loguru logs for every agent turn.
    """

    async def before_run_callback(
        self,
        *,
        invocation_context: InvocationContext,
        **kwargs: Any,
    ) -> None:
        """
        Inject context into current OTEL span and bind it to Loguru.
        """
        session_id = invocation_context.session.id
        user_id = invocation_context.user_id

        # Inject into OpenTelemetry Current Span
        current_span = get_current_span()
        if current_span.is_recording():
            current_span.set_attribute("session_id", session_id)
            if user_id:
                current_span.set_attribute("user_id", user_id)

        # Inject into Loguru Context
        # Loguru 'contextualize' is a context manager. To apply it to the whole run,
        # we can bind the variables to the logger instance.
        logger.configure(extra={"session_id": session_id, "user_id": user_id})

        # Log the start of the turn
        logger.info(f"Agent Turn started for Session ID: {session_id}")
