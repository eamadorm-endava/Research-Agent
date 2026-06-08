from typing import Any, Optional
from google.adk.auth.auth_tool import AuthConfig
from google.adk.tools import BaseTool, ToolContext
from google.adk.tools.base_toolset import BaseToolset
from google.genai import types
from loguru import logger

from google.adk.events.event import Event


class FileIngestionToolWrapper(BaseTool):
    """Wraps an existing ADK Tool to intercept its output and auto-inject GCS URIs mid-turn.

    When an MCP Tool or a Tool returns a dictionary with `_inject_file_data = True`, this wrapper
    intercepts the response and automatically appends a types.Part(file_data=...) directly
    into the active session's event history. This allows the LLM to access the file in its
    very next reasoning loop without requiring a separate turn or tool call.
    """

    def __init__(self, original_tool: BaseTool) -> None:
        """Initializes the wrapper by mirroring the original tool's metadata.

        Args:
            original_tool: BaseTool -> The tool to be wrapped and intercepted.

        Returns:
            None -> Initializes the wrapper.
        """
        super().__init__(
            name=original_tool.name,
            description=original_tool.description,
            is_long_running=original_tool.is_long_running,
            custom_metadata=original_tool.custom_metadata,
        )
        self.original_tool = original_tool

    def _get_declaration(self) -> Optional[types.FunctionDeclaration]:
        """Returns the function declaration for Gemini model configuration.

        Args:
            None -> No arguments required.

        Returns:
            Optional[types.FunctionDeclaration] -> The original tool's declaration.
        """
        return self.original_tool._get_declaration()

    def _inject_file_into_session(
        self, gcs_uri: str, mime_type: str, tool_context: ToolContext
    ) -> None:
        """Injects a file directly into the session's event history.

        Args:
            gcs_uri: str -> The GCS URI of the file.
            mime_type: str -> The MIME type of the file.
            tool_context: ToolContext -> The active tool context.

        Returns:
            None -> Modifies the session history in place.
        """
        logger.info(f"Auto-injecting GCS URI into LLM context mid-turn: {gcs_uri}")
        part = types.Part(
            file_data=types.FileData(file_uri=gcs_uri, mime_type=mime_type)
        )
        injection_event = Event(
            author="user",
            content=types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=f"System Notification: The requested file ({gcs_uri}) has been automatically injected into the context."
                    ),
                    part,
                ],
            ),
        )

        session = tool_context._invocation_context.session
        session.events.append(injection_event)
        logger.debug(f"Successfully appended injection event for {gcs_uri}")

    async def run_async(
        self, *, args: dict[str, Any], tool_context: ToolContext
    ) -> dict[str, Any]:
        """Executes the wrapped tool and intercepts _inject_file_data signals.

        Args:
            args: dict[str, Any] -> The arguments passed to the tool.
            tool_context: ToolContext -> The active tool context.

        Returns:
            dict[str, Any] -> The tool's execution result.
        """
        result = await self.original_tool.run_async(
            args=args, tool_context=tool_context
        )

        if (
            self.original_tool.name == "read_object"
            and isinstance(result, dict)
            and result.get("execution_status") == "success"
        ):
            result["_inject_file_data"] = True
            metadata = result.get("metadata", {})
            result["mime_type"] = metadata.get("mime_type", "application/pdf")

        if not isinstance(result, dict) or not result.get("_inject_file_data"):
            return result

        gcs_uri = result.get("gcs_uri")
        if not gcs_uri:
            return result

        mime_type = result.get("mime_type", "application/octet-stream")

        try:
            self._inject_file_into_session(gcs_uri, mime_type, tool_context)

            result["execution_message"] = (
                f"{result.get('execution_message', 'Success.')} "
                f"The file has been injected into the conversation context as a system message. "
                f"You may now proceed to analyze it."
            )
        except Exception as e:
            logger.error(f"Failed to auto-inject {gcs_uri}: {e}")
            result["execution_status"] = "error"
            result["execution_message"] = f"Failed to inject file {gcs_uri}: {e}"

        return result


class FileIngestionToolsetWrapper(BaseToolset):
    """Wraps an entire ADK BaseToolset to ensure all its underlying tools get intercepted."""

    def __new__(cls, original_toolset: BaseToolset) -> Any:
        """Creates a dynamic subclass of FileIngestionToolsetWrapper named after the original toolset class.

        This guarantees that ADK's logging and debugging outputs print the original toolset's name (e.g. McpToolset)
        instead of the generic wrapper class name.
        """
        original_class = original_toolset.__class__
        class_name = original_class.__name__
        dynamic_subclass = type(class_name, (cls,), {})
        instance = super(FileIngestionToolsetWrapper, dynamic_subclass).__new__(
            dynamic_subclass
        )
        return instance

    def __init__(self, original_toolset: BaseToolset) -> None:
        """Initializes the wrapper for the given toolset.

        Args:
            original_toolset: BaseToolset -> The toolset to be wrapped.
        """
        super().__init__(
            tool_filter=getattr(original_toolset, "tool_filter", None),
            tool_name_prefix=getattr(original_toolset, "tool_name_prefix", None),
        )
        self.original_toolset = original_toolset

    async def get_tools(self, readonly_context: Optional[Any] = None) -> list[BaseTool]:
        """Retrieves and wraps all tools from the original toolset.

        Args:
            readonly_context: Optional context passed by the framework.

        Returns:
            list[BaseTool] -> A list of FileIngestionToolWrapper instances wrapping the original tools.
        """
        original_tools = await self.original_toolset.get_tools(readonly_context)
        return [FileIngestionToolWrapper(tool) for tool in original_tools]

    def get_auth_config(self) -> Optional[AuthConfig]:
        """Delegates auth config retrieval to the original toolset.

        Returns:
            Optional[AuthConfig] -> The auth config of the original toolset.
        """
        return self.original_toolset.get_auth_config()

    async def close(self) -> None:
        """Closes the original toolset."""
        await self.original_toolset.close()

    async def process_llm_request(self, *, tool_context: Any, llm_request: Any) -> None:
        """Processes the outgoing LLM request using the original toolset."""
        await self.original_toolset.process_llm_request(
            tool_context=tool_context, llm_request=llm_request
        )
