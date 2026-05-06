import pytest
from datetime import datetime
from agent.core_agent.tools.time_tools import GetCurrentTimeTool


@pytest.mark.asyncio
async def test_get_current_time_success():
    """
    Test that the tool returns a valid ISO 8601 string in Central Time.

    Happy Path:
    - Should return execution_status='success'
    - Should return current_time in ISO format
    - Should have America/Chicago timezone
    """
    tool = GetCurrentTimeTool()
    # tool_context is not used in this tool, so we can pass None
    result = await tool.run_async(args={}, tool_context=None)

    assert result["execution_status"] == "success"
    assert "current_time" in result
    assert result["timezone"] == "America/Chicago"

    # Validate ISO format
    dt = datetime.fromisoformat(result["current_time"])
    assert dt.tzinfo is not None

    # Validate timezone offset for America/Chicago (CST is -6, CDT is -5)
    # Note: This might change depending on the time of year, but it should be one of these two.
    offset = dt.utcoffset().total_seconds() / 3600
    assert offset in [-6.0, -5.0]


def test_tool_declaration():
    """
    Test that the tool declaration is correct.
    """
    tool = GetCurrentTimeTool()
    declaration = tool._get_declaration()

    assert declaration.name == "get_current_time"
    assert "Central Time" in declaration.description
    assert declaration.parameters.type == "OBJECT"
    assert len(declaration.parameters.properties) == 0
