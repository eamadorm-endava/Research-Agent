---
trigger: always_on
glob: "**/*"
description: "Development lifecycle protocols: Stage 1 (Prototyping/Notebooks) vs Stage 2 (Deployment/Terraform)."
---

# development-guide.md

This guide defines the mandatory lifecycle for developing, verifying, and promoting deployable components in the Research-Agent project.

## The Two-Issue Strategy
Every deployable feature (e.g., `smae_engine`, `nutrient_agent`) must be split into **two distinct GitHub issues**:
1. **Issue Part A**: Stage 1 - Prototyping & Scripting.
2. **Issue Part B**: Stage 2 - Infrastructure Deployment.

### Issue Requirements
- **Mandatory Isolation**: Each GitHub issue must represent ONLY ONE stage. Do not combine prototyping and deployment in a single issue.
- **Granularity**: If a feature is large, its Stage 1 (Part A) implementation must be split into multiple, smaller issues.
- **Sequential Dependency**: A Stage 2 (Part B) issue can **ONLY** begin once **all** associated Stage 1 (Part A) issues have been solved and merged into the `main` branch.

---

## Stage 1: Prototyping (Mandatory)
The goal of Stage 1 is to prove the logic works using manual infrastructure before codifying it in Terraform. This stage triggers the **`@.agents/skills/prototyping-logic/SKILL.md`** skill.

### 1. Folder Structure
All application logic, scripts, and processing code must reside in their respective root folders based on component type:
- `agent/<deployable_name>/` (for ADK logic)
- `mcp_servers/<deployable_name>/` (for MCP components)
- `pipelines/<deployable_name>/` (for data pipelines)

### 2. Manual Infrastructure Scripts
If the scripts require GCP resources (GCS, BigQuery, Secret Manager only), they must be managed via two bash scripts in the deployable root:
- `create_resources.sh`: Contains `gcloud` commands to create the environment.
- `delete_resources.sh`: Contains `gcloud` commands to tear down the environment.

### 3. Verification Protocol (Notebooks)
A Jupyter Notebook must be created to demonstrate the functionality:
- **Location**: `notebooks/<deployable_name>/<notebook_name>.ipynb`.
- **Requirements**:
  - Must use `import sys; sys.path.append("../..")` to correctly import modules from the project root.
  - Must show successful execution, edge case handling, and data validation.

### 4. Implementation Cycle
For each component or feature, the implementation must follow this iterative loop:
1.  **Logic Development**: Build the scripts in the respective package root (e.g., `app/`, `core_agent/`). 
    - **Requires**: All code MUST adhere strictly to the universal principles in `@.agents/rules/coding-guide.md` (DRY, SRP, intent-based naming).
    - **Applies**: Reference `@.agents/rules/backend-guide.md` and `@.agents/rules/mcp-server-guide.md` for implementation standards.
2.  **Cybersecurity Audit**: Generate a `cybersec_report.md`. 
    - **Requires**: Follow `@.agents/rules/cybersecurity-guide.md`.
    - **Triggers**: Use the `@.agents/skills/security-audit/SKILL.md` skill.
3.  **Test Generation**: Create unit tests in the component's test directory, typically `agent/tests/` or `mcp_servers/<deployable_name>/tests/`.
    - **Applies**: Follow the `@.agents/rules/tests-guide.md` (Success, Failure, and Edge Cases).
    - Iterate until 100% of tests pass.
4.  **Verification**: After passing Cybersec and Tests, create the **Jupyter Notebook** in `notebooks/` for final demonstration.

### 5. Commit Protocol
To maintain a clean and traceable history, follow these rules:
- **Frequent Commits**: Commit logically complete units of work regularly. Do not wait until the entire feature is done.
- **File Limit**: Each commit must **never exceed 5 modified files**.
- **Linting**: Every commit must represent a stable, linted, and functional state.

### 6. User Review & PR Protocol
1.  **Satisfaction Loop**: Iterate on the logic and notebooks until the user is explicitly satisfied.
2.  **PR Request**: Only once satisfied, ask the user for permission to create the Pull Request.
3.  **PR Content**: Every PR must include:
    - A brief and clear description of the purpose.
    - Highlights of important changes or additions.

### 7. Stage 1 Definition of Done (DoD)
- Logic implemented and passing all tests (including edge cases).
- Cybersecurity status: 0 High, ≤ 2 Medium.
- Notebook approved by the user.
- **Manual infrastructure deleted** via `delete_resources.sh`.

---

## Stage 2: Infrastructure Deployment
Stage 2 begins only after Stage 1 is fully merged. This stage triggers the **`@.agents/rules/devops-guide.md`** standards and the **`@.agents/skills/deployment/SKILL.md`** skill.

### 1. Codification (Terraform)
The infrastructure requirements proven in Stage 1 must be codified in:
`terraform/<deployable_name>_resources/` (e.g., `gcs_mcp_server_resources`).
- Use **Cloud Foundation Fabric (CFF)** modules.
- Ensure all resources (GCS, BQ, etc.) match the logic approved in the Notebook.

### 2. CI/CD Triggers
All Cloud Build triggers must be created/updated via the centralized script:
`terraform/scripts/cicd_triggers_creation.sh`.
- **RULE**: Cloud Build triggers must **NEVER** be managed via Terraform. 
- Triggers must be functional and tested before merging.

### 3. Stage 2 Definition of Done (DoD)
- Terraform modules applied successfully.
- CI/CD triggers functional (tested via `cicd_triggers_creation.sh`).
- PR merged into `main`.
