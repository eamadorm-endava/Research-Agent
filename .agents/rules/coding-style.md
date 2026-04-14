---
trigger: always_on
---

# Coding Style Guidelines

This document outlines the standards and best practices for developing in the Research Agent repository.

## 1. Tooling & Dependency Management

- **Manager**: Use [uv](https://github.com/astral-sh/uv) for all Python environment management.
- **Dependency Groups**: For every MCP server, agent, or major feature requiring its own dependencies, create a dedicated group in `pyproject.toml`.
  - *Example*: `mcp_calendar`, `ai-agent`.
- **Execution**: Always use `uv run` to ensure dependencies are resolved within the correct group context.

## 2. Testing

- **Framework**: Use `pytest` for all unit and integration tests.
- **Makefile Integration**: Prefer using the existing `Makefile` commands for local test execution to ensure consistent environments.
  - `make test-agent`: Run AI agent tests.
  - `make run-bq-tests`: Run BigQuery MCP tests.
  - `make run-drive-tests`: Run Google Drive MCP tests.

## 3. Documentation (Docstrings)

### Classes
All classes must include a concise docstring (1 or 2 lines) indicating its function or primary responsibility.

### Methods and Functions
All functions and methods must include docstrings following this specific structure:
1. **Brief Description**: 2 or 3 lines summarizing the purpose.
2. **Args**: List of arguments with types and descriptions.
3. **Returns**: Description of the return value and its type.

**Constraint**: Individual functions or methods must not exceed **60 lines** in total, including docstrings and empty lines. If a function exceeds this limit, it should be refactored into smaller, modular components.

*Example*:
```python
class DurationCalculator:
    """Helper class to manage and format time durations for API responses."""

    def calculate_duration(self, initial_time: datetime, final_time: datetime) -> str:
        """Calculates the duration between two datetime objects.
        Ensures the output is formatted as a human-readable string.

        Args:
            initial_time (datetime): The starting time.
            final_time (datetime): The ending time.

        Returns:
            str: Formatted duration string (e.g., '1h 25m 30s').
        """
```

## 4. Configuration Management

- **config.py**: All configuration values and environment variables must be managed in a `config.py` file.
- **Pydantic Settings**: Use `BaseSettings` from `pydantic-settings` to define configuration models.
- **Subclasses**: Organize configuration into logical subclasses if the module handles multiple distinct settings areas.

## 5. Data Validation and Schemas

- **Pydantic**: Use [Pydantic v2](https://docs.pydantic.dev/latest/) `BaseModel` for all data structures, API responses, and internal schemas.
- **Annotated**: Use `Annotated` and `Field` to provide metadata and descriptions for schema attributes.

- **Pydantic**: Use [Pydantic v2](https://docs.pydantic.dev/latest/) `BaseModel` for all data structures, API responses, and internal schemas.
- **Annotated**: Use `Annotated` and `Field` to provide metadata and descriptions for schema attributes.

## 7. Type Hinting

- **Precision**: Iterators must have at least one level of precision (e.g., `list[str]`, `dict[str, int]`).
- **Syntax**: Use lowercase `list` and `dict` instead of capitalized `List` and `Dict`.
- **Unions**: Use `Union` from the `typing` module (e.g., `Union[str, int]`) instead of the `|` operator for broader compatibility.
- **Avoid Any**: Avoid using `Any` where possible; prefer `Union` of specific primitives (e.g., `Union[str, int, float, bool]`).

## 9. Naming Conventions

- **snake_case**: Use `snake_case` for all variables, functions, methods, and class attributes.
- **CamelCase**: Use `PascalCase` (CamelCase with a capitalized first letter) for all class names.

## 10. Logging

- Use logger library for logs, the logs of private methods must be of type debug, whereas exposed/public methods and functions must be of type info.