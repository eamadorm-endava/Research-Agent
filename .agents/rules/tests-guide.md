---
trigger: always_on
glob: "**/*"
description: "Universal testing protocols: Success, Failure, and Edge case verification."
---

# tests-guide.md

Adhere to these universal testing principles to ensure code reliability:
- **Enforces**: `@.agents/rules/coding-guide.md` for naming and structure.
- **References**: `@.agents/rules/development-guide.md` for where testing fits in the lifecycle.

- **The Trinity of Testing**: Every unit of logic must be validated against three distinct scenarios:
  - **Happy Path**: Standard, valid inputs that produce the expected success outcome.
  - **Edge Cases**: Boundary conditions (e.g., empty strings, zero values, maximum lengths, or null/undefined types).
  - **Failure Modes**: Invalid or malicious inputs; verify that the system raises the correct errors rather than crashing.
- **Test Isolation**: Each test must be independent. The success or failure of one test should never depend on the execution order or the state left by a previous test.
- **Mocking Externalities**: Never let tests rely on external volatile factors (APIs, databases, or system clocks). Use "Mocks" or "Stubs" to simulate these dependencies so you are testing your logic, not the network.
- **Deterministic Outcomes**: Tests must be idempotent. Running the same test 100 times with the same input must yield the same result 100 times.
- **Descriptive Naming**: Test names must act as documentation. Use a "Should/When" or "Given/When/Then" pattern (e.g., `CalculateTax_ShouldReturnZero_WhenIncomeIsNegative`).
- **Assertion Specificity**: Avoid "truthy" checks. Assert for the exact value, type, or exception expected to prevent "false positives."
- **Setup and Teardown**: Use clean-up routines to ensure the environment is reset after every test execution.
- **Regression Protocol**: When a bug is found, write a test that reproduces it before fixing the code. This ensures the bug never reappears.
