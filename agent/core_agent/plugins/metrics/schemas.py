from datetime import datetime
from typing import Annotated, Optional
from pydantic import BaseModel, Field


class ToolUsageRecord(BaseModel):
    """Schema representing metrics for a single tool invocation."""

    tool_name: Annotated[
        str, Field(description="The name of the tool that was executed")
    ]
    initial_time: Annotated[
        datetime,
        Field(description="Timestamp indicating when the tool started executing"),
    ]
    final_time: Annotated[
        Optional[datetime],
        Field(
            description="Timestamp indicating when the tool completed execution",
            default=None,
        ),
    ]
    tool_full_time: Annotated[
        Optional[float],
        Field(
            description="Total duration of the tool execution in seconds", default=None
        ),
    ]


class MetricsRecord(BaseModel):
    """Schema representing metrics for an entire agent invocation/turn."""

    session_id: Annotated[
        str, Field(description="Unique identifier for the agent session")
    ]
    user_id: Annotated[
        Optional[str],
        Field(
            description="Identifier for the user initiating the session", default=None
        ),
    ]
    prompt_id: Annotated[
        str, Field(description="Unique identifier for the turn invocation (prompt ID)")
    ]
    prompt: Annotated[
        Optional[str],
        Field(description="Text content of the user prompt", default=None),
    ]
    agent_response: Annotated[
        Optional[str],
        Field(description="Text content of the final agent response", default=None),
    ]
    initial_time: Annotated[
        datetime,
        Field(description="Timestamp indicating when the user prompt was received"),
    ]
    final_time: Annotated[
        Optional[datetime],
        Field(
            description="Timestamp indicating when the final agent response was ready",
            default=None,
        ),
    ]
    time_to_answer: Annotated[
        Optional[float],
        Field(
            description="Total time taken to process the turn in seconds", default=None
        ),
    ]
    tools_used: Annotated[
        list[ToolUsageRecord],
        Field(
            description="List of all tools invoked during this agent turn",
            default_factory=list,
        ),
    ]
