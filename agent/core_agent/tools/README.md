# ADK Tools Documentation

This directory contains the custom tools registered with the ADK `AgentBuilder`. 

## Implementation Standards
All ADK tools must follow these structural requirements:

1. **Inherit from `BaseTool`**: Your tool class must extend `google.adk.tools.BaseTool`.
2. **Implement `_get_declaration()`**: You must override this method to provide the Gemini `types.FunctionDeclaration`. This tells the LLM what the tool does and what parameters it requires.
3. **Async Execution**: The business logic must be implemented inside an asynchronous `run_async(self, ...)` or `execute(...)` method as expected by the ADK wrapper.
4. **Configuration**: If your tool requires environment variables (e.g., URLs, API keys), define a `config.py` in your tool's folder using Pydantic `BaseSettings`.
