---
trigger: always_on
glob: "**/*"
description: "Language-agnostic programming standards for architecture, readability, and maintainability."
---

# coding-style.md

Follow these universal engineering standards:

- **DRY & Simple**: Do not repeat logic. If a pattern appears three times, abstract it. Avoid overengineering; favor readability over "clever" code.
- **OOP Principles**: Use Object-Oriented patterns to encapsulate state and behavior. Prefer **Composition over Inheritance**.
- **Single Responsibility (SRP)**: Each class, module, and function must have one—and only one—reason to change.
- **Refactoring Rule**: Each function/method must not be greater than **50 lines** of code. If so, assess the possibility to split functionality into different functions following the Single Responsibility Principle.
- **Fail Fast**: Use "Guard Clauses" to return early. Avoid deeply nested `if/else` structures (The Arrow Anti-pattern).
- **Intent-Based Naming**: Use descriptive names for variables and functions. Avoid generic terms like `data`, `temp`, or `handle`. Names should reveal *why* the code exists.
- **Documentation (Docstrings)**:
  - **Classes**: Include at the top a brief description of what the class handles.
  - **Methods and Functions**: Must use the following structure:
    ```text
    2 or 3 lines describing what the function does

    Args:
        variable_name: type -> Description of the args

    Returns:
        type -> Description of the return
    ```
- **Logging Strategy**:
  - **INFO**: Log public method entries and major state changes.
  - **DEBUG**: Log internal logic, loops, and data transformations within private methods.
- **Configuration**: Never hardcode values. Use **Config Classes/Objects** to centralize environment variables and constants.
- **Side Effects**: Keep business logic "pure" by separating it from I/O (database, API calls, file system) whenever possible.
- **Typehints**: Try to avoid general typehints such as 'Any'
- **lints**: Make sure that the code is always linted before making any commit
- **Command Automation**: To execute a deployable, generate a Make command, for example, to login to gcloud, wrap the gcloud commands into a make gcloud-auth command, to execute a pipeline, wrap the necessary commands with a make command
 
