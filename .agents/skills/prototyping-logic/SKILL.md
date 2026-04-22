---
name: prototyping-logic
description: Manages the Stage 1 (Prototyping) workflow, including resource script creation, dependency isolation, and Jupyter Notebook verification. Trigger this skill when building the initial logic for a feature.
---

# Prototyping & Logic Skill

This skill governs the execution of Stage 1 (Prototyping) within the Research-Agent project, as defined in `@.agents/rules/development-guide.md`.

## 1. Folder Structure
All application logic, scripts, and processing code must reside in their respective directories:
- `agent/<deployable_name>/`
- `mcp_servers/<deployable_name>/`
- `pipelines/<deployable_name>/`

## 2. Manual Infrastructure Scripts
If the scripts require GCP resources (GCS, BigQuery, Secret Manager only), they must be managed via two bash scripts in the deployable root:
- `create_resources.sh`: Contains `gcloud` commands to create the environment.
- `delete_resources.sh`: Contains `gcloud` commands to tear down the environment.

## 3. Implementation Loop
Execute the following iterative cycle for each component or feature:
1.  **Logic Development**: Build the core scripts in `/source_code`.
2.  **Cybersecurity Audit**: Trigger `@.agents/skills/security-audit/SKILL.md`. Address findings until **0 High/Urgent** and **max 2 Medium** threats remain.
3.  **Test Generation**: Create unit tests in the component's test directory (e.g., `agent/tests/` or `mcp_servers/<deployable_name>/tests/`). Follow @/.agents/rules/tests-guide.md.
4.  **Verification**: Create the **Jupyter Notebook** in `notebooks/` for final demonstration.

## 4. Jupyter Notebook Standard
Location: `notebooks/<deployable_name>/<notebook_name>.ipynb`
- **Mandatory**: Use `import sys; sys.path.append("../..")` to correctly import modules from the project root.
- **Requirements**: Demonstrate successful execution, edge case handling, and data validation.

## 5. Commit & PR Protocol
- **Commits**: Max 5 modified files per commit. Must be stable, linted, and functional.
- **PR Content**: A brief and clear description of the purpose + Highlights of important changes.
- **Cleanup**: Manual infrastructure MUST be deleted via `delete_resources.sh` before PR merge.

## 6. Definition of Done (DoD)
- Logic implemented and passing all tests (including edge cases).
- Cybersecurity status: 0 High, ≤ 2 Medium.
- Notebook approved by the user.
- Manual infrastructure deleted.

## References
- `@.agents/rules/development-guide.md` for full lifecycle definitions.
- `@.agents/rules/tests-guide.md` for testing standards.
- `@.agents/rules/cybersecurity-guide.md` for security protocols.
