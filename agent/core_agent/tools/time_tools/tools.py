from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, override
from google.adk.tools import BaseTool, ToolContext
from google.genai import types
from loguru import logger

from .schemas import GetCurrentTimeResponse


class GetCurrentTimeTool(BaseTool):
    """
    Tool that returns the current time in Central Time (CST/CDT).

    This provides the model with an official way to know the current time
    without relying on potentially stale prompt information.
    """

    def __init__(self) -> None:
        """
        Initializes the time tool.
        """
        super().__init__(
            name="get_current_time",
            description=(
                "Returns the current date and time in ISO 8601 format for the Central Time zone. "
                "Use this to orient yourself in time or provide accurate timestamps to the user."
            ),
        )

    def _get_declaration(self) -> Optional[types.FunctionDeclaration]:
        """
        Builds the Gemini function declaration schema for this tool.

        Returns:
            Optional[types.FunctionDeclaration] -> Schema describing the tool's parameters.
        """
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={},
                required=[],
            ),
        )

    @override
    async def run_async(self, *, args: dict, tool_context: ToolContext) -> dict:
        """
        Executes the tool to get the current time.

        Args:
            args: dict -> Ignored for this tool.
            tool_context: ToolContext -> ADK context.

        Returns:
            dict -> Serialized GetCurrentTimeResponse.
        """
        logger.info("Fetching current time in Central Time")
        try:
            # Central Time (America/Chicago)
            tz = ZoneInfo("America/Chicago")
            now = datetime.now(tz)

            response = GetCurrentTimeResponse(
                current_time=now.isoformat(), timezone="America/Chicago"
            )
            return response.model_dump()
        except Exception as e:
            logger.error(f"Error getting current time: {e}")
            return {"execution_status": "error", "execution_message": str(e)}
