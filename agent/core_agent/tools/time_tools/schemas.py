from typing import Annotated
from pydantic import BaseModel, Field


class GetCurrentTimeResponse(BaseModel):
    """
    Response containing the current time and timezone info.
    """

    current_time: Annotated[
        str, Field(description="The current time in ISO 8601 format")
    ]
    timezone: Annotated[
        str, Field(description="The timezone used (e.g. America/Chicago)")
    ]
    execution_status: Annotated[
        str, Field(description="Status of the tool execution", default="success")
    ]
