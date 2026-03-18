# Authentication Documentation

This directory contains the documentation regarding how the AI Agent securely authenticates with the external MCP Servers to access Google Cloud resources.

## Reading Order

We recommend reading the documents in the following order:

1. **[01-Auth-Methods.md](01-Auth-Methods.md)**: Architectural comparison (OAuth vs DWD) and how the authentication natively works with Gemini Enterprise.
2. **[02-a-Setup-OAuth.md](02-a-Setup-OAuth.md)**: Step-by-step guide to configure the recommended Per-User OAuth 2.0 flow.
3. **[02-b-Setup-DWD.md](02-b-Setup-DWD.md)**: Step-by-step guide to configure Domain-Wide Delegation (Legacy/Alternative).
4. **[03-OAuth-Flow.md](03-OAuth-Flow.md)**: In-depth technical lifecycle of the OAuth token across the ADK, Frontend, and MCP layers.
