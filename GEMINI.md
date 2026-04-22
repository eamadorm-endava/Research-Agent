# GEMINI.md (Master Protocol Anchor)

Follow this execution pipeline for every task. This document acts as the master anchor for repository-specific standards and mandatory development protocols.

---

### Phase 1: Discovery
Focus on understanding requirements, architecting the solution, and planning.
*   **Architectural Blueprint**: Read `@.agents/rules/architecture-guide.md`.
*   **Technical Planning**: This phase triggers the `@.agents/skills/architecture-planning/SKILL.md` skill to generate plans and manage GitHub entities.

---

### Phase 2: Prototyping
Focus on implementing logic, verifying functionality, and ensuring security.
*   **Lifecycle Management**: Strictly follow the **`@.agents/rules/development-guide.md`**.
*   **Prototyping Workflow**: Trigger the specialized skill:
    - **Skill**: `@.agents/skills/prototyping-logic/SKILL.md`
*   **Domain Standards**:
    - **Agent Logic**: Reference `@.agents/rules/backend-guide.md`.
    - **MCP Servers**: Reference `@.agents/rules/mcp-server-guide.md`.
    - **Quality Assurance**: Use `@.agents/rules/tests-guide.md`.
*   **Security & Compliance**:
    - **Standards**: Follow `@.agents/rules/cybersecurity-guide.md`.
    - **Audit**: Always trigger `@.agents/skills/security-audit/SKILL.md` before finalizing logic.
*   **Universal Standards**: All code must enforce `@.agents/rules/coding-guide.md`.

---

### Phase 3: Deployment
Focus on infrastructure codification and production release.
*   **Infrastructure Standards**: Reference `@.agents/rules/devops-guide.md`.
*   **Deployment Workflow**: Trigger the specialized skill:
    - **Skill**: `@.agents/skills/deployment/SKILL.md`

---

> **Golden Rule**: Keep it simple. Follow the `@.agents/rules/development-guide.md` lifecycle without exceptions. Phase 3 never begins until Phase 2 is fully merged.
