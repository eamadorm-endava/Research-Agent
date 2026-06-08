# Tool Wrappers

This directory contains classes that intercept and wrap existing ADK tools.

Unlike standard ADK callbacks (which hook into predefined lifecycle moments), tool wrappers implement the `BaseTool` or `BaseToolset` interface directly. They wrap the original tool, execute it, and then apply arbitrary logic to modify or intercept the output before returning it to the LLM.
