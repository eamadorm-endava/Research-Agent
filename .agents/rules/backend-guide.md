---
trigger: always_on
glob: "**/*.py"
description: "Python backend standards: uv management, Pydantic AI, MCP, and Request/Response schemas."
---

# backend-guide.md

All backend development must strictly adhere to these Python-specific protocols:

### Environment & Execution
- **Dependency Management**: Use `uv` exclusively. Never run `python` directly.
- **Execution Commands**: Always use `--group` for specific deployables.
  - *Script*: `uv run --group <group-name> python -m path.to.script`
  - *Testing*: `uv run pytest`
  - *Linting*: `uv run precommit`

### Data Architecture & Validation
- **Pydantic Usage**: 
  - Use `BaseSettings` for all configuration classes.
  - Use `BaseModel` for public method schemas.
- **Public Method Pattern**: For complex public methods or those requiring a specific pattern, always implement distinct input and output schemas:
  - `<Action>Request(BaseModel)`: To encapsulate all input parameters.
  - `<Action>Response(BaseModel)`: To encapsulate the returned data.
- **Return Values**: Never use tuples for multiple returns. Always return a `dict` for internal logic or a `BaseModel` for public outputs.
  - Public methods: Return Pydantic `Response` schemas.
  - Private methods: Return dictionaries.
- **Attribute Definition**: Subclasses of `BaseModel`/`BaseSettings` must use `Annotated`:
  - Format: `attribute: Annotated[type, Field(description="...", default=...)]`
  - **Type Reuse**: If an attribute definition is repeated, create a reusable type alias using `Annotated`.

### AI & Integration
- **AI Agents**: Use the **Vertex AI Agent Engine (ADK)** for all agent logic and orchestration.
- **MCP Servers**: Use the **MCP Python SDK** for Model Context Protocol implementations.
- **Logging**: Use **loguru** for all logging tasks.

### Naming & Type Hinting
- **Enforces**: All code must adhere to the universal principles defined in **`@.agents/rules/coding-guide.md`** (DRY, SRP, intent-based naming). Below are the Python-specific extensions.
- **Naming Conventions**: 
  - `CamelCase` for classes (e.g., `ProcessDataRequest`).
  - `snake_case` for variables, attributes, and methods.
- **Strict Typing**:
  - Always use type hints; `Any` is strictly forbidden unless absolutely necessary.
  - Use lowercase built-ins: `list[]`, `dict[]`, `tuple[]` instead of `List`, `Dict`, `Tuple`.
  - **Two-Layer Depth**: Limit nested hints to two levels (e.g., `dict[str, list]`).
  - **Modern Syntax**: Use `Self`, `Optional`, and `Union` from `typing`.
  - **No String Hints**: Never use string forward references for types.

### Implementation Example
```python
from typing import Annotated, Self, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# Reusable type alias
DescriptionType = Annotated[str, Field(description="Detailed item description", max_length=500)]

class ListFilesRequest(BaseModel):
    directory_path: Annotated[str, Field(description="Target directory to scan")]
    recursive: Annotated[bool, Field(description="Whether to scan subdirectories", default=False)]

class ListFilesResponse(BaseModel):
    files: Annotated[list[str], Field(description="List of file paths found")]
    count: Annotated[int, Field(description="Total number of files")]

class StorageConfig(BaseSettings):
    base_path: Annotated[str, Field(description="Root storage path", default="/tmp")]

    class Config:
        env_prefix = "STORAGE_"

def list_directory_contents(self, request: ListFilesRequest) -> ListFilesResponse:
    """
    Public method using specific Request/Response pattern.
    """
    # Internal logic...
    results = ["file1.txt", "file2.json"]
    return ListFilesResponse(files=results, count=len(results))
