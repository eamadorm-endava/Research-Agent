import json
from typing import Any, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools import BaseTool, ToolContext
from google.genai import types
from loguru import logger


class MultimodalFileInjectionPlugin(BasePlugin):
    """Intercepts LlmRequests and injects FileData when a tool returns `inject_file_data`.

    Unlike appending to session.events mid-turn (which can break the strict alternating
    user-model sequence required by the Vertex AI API), this plugin modifies the
    `LlmRequest` immediately before it is sent to the LLM. It scans the tool response
    for the `inject_file_data` flag, and if found, appends the native multimodal
    attachment directly into the same `Content` block.
    """

    def __init__(self) -> None:
        """Initializes the multimodal file injection plugin.

        Args:
            None

        Returns:
            None -> Initializes the plugin with a predefined name.
        """
        super().__init__(name="multimodal_file_injection_plugin")

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict]:
        """Injects user dependencies into MCP tools before they execute.

        Args:
            tool: BaseTool -> The tool instance that is about to be executed.
            tool_args: dict[str, Any] -> The arguments dictionary.
            tool_context: ToolContext -> The active tool execution context.

        Returns:
            Optional[dict] -> None, to allow execution with modified arguments.
        """
        # We only inject if 'request' is present in the arguments (indicates a typed Request model)
        if "request" not in tool_args:
            return None

        try:
            logger.debug(
                f"MultimodalFileIngestionPlugin - Injecting Landing Zone dependencies into {tool.name}"
            )
            session = tool_context._invocation_context.session
            user_id = getattr(session, "user_id", "unknown-user")
            session_id = getattr(session, "id", "unknown-session")
            app_name = "core_agent"

            # Create or update the dependencies dict
            tool_args["request"]["dependencies"] = {
                "app_name": app_name,
                "user_id": str(user_id),
                "session_id": str(session_id),
            }
            logger.debug(
                f"Dependencies injected = {tool_args['request']['dependencies']}"
            )

        except Exception as e:
            logger.warning(
                f"MultimodalFileIngestionPlugin - Failed to inject dependencies: {e}"
            )

        return None

    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict,
    ) -> Optional[dict]:
        """Intercepts tool execution to format success/error messages.

        Args:
            tool: BaseTool -> The tool instance that just executed.
            tool_args: dict[str, Any] -> The original tool arguments.
            tool_context: ToolContext -> The active tool execution context.
            result: dict -> The raw result dictionary returned by the tool.

        Returns:
            Optional[dict] -> The modified result dictionary, or None to keep original.
        """
        if not isinstance(result, dict):
            return None

        payload = result.get("structuredContent", result)
        if not isinstance(payload, dict) or not payload.get("inject_file_data"):
            return None

        gcs_uri = payload.get("gcs_uri")
        if gcs_uri:
            payload["execution_message"] = (
                f"File {gcs_uri} was securely copied to the internal Landing Zone "
                f"and has been injected into the multimodal context!"
            )

        return None

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> Optional[LlmResponse]:
        """Intercepts the model request to inject FileData if signaled by a tool.

        Args:
            callback_context: CallbackContext -> Context of the current agent call.
            llm_request: LlmRequest -> The request about to be sent to the model.

        Returns:
            Optional[LlmResponse] -> Always returns None to allow the request to proceed.
        """
        if not llm_request.contents:
            return None

        # Look for a tool response in the contents
        for content in llm_request.contents:
            if not content.parts:
                continue

            for part in content.parts:
                if not part.function_response:
                    continue

                # In the ADK, function_response.response is typically a dict
                response_dict = part.function_response.response

                # Sometimes the framework serializes it as a Struct or string, handle dict
                if not isinstance(response_dict, dict):
                    try:
                        # Attempt to parse if it's a string, or just skip
                        if isinstance(response_dict, str):
                            response_dict = json.loads(response_dict)
                        else:
                            continue
                    except Exception:
                        continue

                # We need to dig into the nested "structuredContent" if ADK wrapped it
                payload = response_dict.get("structuredContent", response_dict)

                if isinstance(payload, dict) and payload.get("inject_file_data"):
                    gcs_uri = payload.get("gcs_uri")
                    mime_type = payload.get("mime_type")

                    if gcs_uri and mime_type:
                        logger.info(
                            f"MultimodalFileInjectionPlugin intercepted tool response. "
                            f"Injecting file data into LlmRequest: {gcs_uri}"
                        )
                        # Inject the file data directly into the content parts
                        content.parts.append(
                            types.Part(
                                file_data=types.FileData(
                                    file_uri=gcs_uri, mime_type=mime_type
                                )
                            )
                        )
                        # We don't need to pop the flag since the LLM request is transient
                        # but we do it to keep the LLM payload clean
                        payload.pop("inject_file_data", None)

                        # Re-assign if we parsed it from a string
                        if isinstance(part.function_response.response, str):
                            part.function_response.response = json.dumps(response_dict)

        return None
