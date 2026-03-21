import logging
import re
from typing import Any

import yaml
from typing_extensions import override

from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.debug_logging_plugin import DebugLoggingPlugin


logger = logging.getLogger(__name__)


_REDACTED_VALUE = "<redacted>"
_SENSITIVE_KEYS = {
    "clientsecret",
    "accesstoken",
    "refreshtoken",
    "idtoken",
    "token",
    "authorization",
    "x-serverless-authorization",
}


def _redact_sensitive(data: Any) -> Any:
    if isinstance(data, dict):
        redacted: dict[str, Any] = {}
        for key, value in data.items():
            normalized_key = str(key).replace("_", "").replace("-", "").lower()
            if normalized_key in _SENSITIVE_KEYS:
                redacted[key] = _REDACTED_VALUE
                continue

            redacted[key] = _redact_sensitive(value)
        return redacted

    if isinstance(data, list):
        return [_redact_sensitive(item) for item in data]

    if isinstance(data, str):
        if data.startswith("Bearer "):
            return _REDACTED_VALUE

        if re.search(r"(client_secret=|refresh_token=|access_token=)", data):
            return _REDACTED_VALUE

    return data


class CloudLoggingDebugPlugin(DebugLoggingPlugin):
    """Emit ADK invocation debug data to application logs instead of a local file."""

    def __init__(self):
        super().__init__(
            output_path="/tmp/adk_debug.yaml",
            include_session_state=False,
            include_system_instruction=False,
        )

    @override
    async def after_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> None:
        """Log the captured invocation trace and avoid writing sensitive state to disk."""
        invocation_id = invocation_context.invocation_id

        if invocation_id not in self._invocation_states:
            logger.warning(
                "No debug state for invocation %s, skipping write",
                invocation_id,
            )
            return

        state = self._invocation_states[invocation_id]
        self._add_entry(invocation_id, "invocation_end")

        try:
            output_data = state.model_dump(mode="json", exclude_none=True)
            output_data = _redact_sensitive(output_data)
            logger.info(
                "ADK invocation debug trace\n%s",
                yaml.safe_dump(
                    output_data,
                    allow_unicode=True,
                    sort_keys=False,
                    width=120,
                ),
            )
        except Exception:
            logger.exception(
                "Failed to serialize debug data for invocation %s",
                invocation_id,
            )
        finally:
            self._invocation_states.pop(invocation_id, None)