---
name: architecture-planning
description: Coordinates the Discovery Phase, generates Implementation Plans, and manages GitHub Issues/Milestones according to the Part A/Part B standard. Trigger this skill whenever you need to design a new feature or refactor existing modules.
---

# Architecture & Planning Skill

This skill handles the technical design and project management orchestration for the Research-Agent project.

## 1. Discovery Q&A
Before generating any plans or issues:
- **Initiate Q&A**: Ask the user strategic questions to clarify the feature scope, architecture choices, and integration points.
- **Approval**: Proceed to planning only after the user has confirmed the high-level approach.

## 2. Implementation Plan Generation
After getting all the necessary context and information from the user, generate a markdown plan with:
- **Folder Structure**: Use the repository structure:
    - `agent/<name>/` for ADK capabilities
    - `mcp_servers/<name>/` for MCP server implementations
    - `pipelines/<name>/` for data ingestion
    - `terraform/<name>_resources/` for infrastructure
- **Shared Infrastructure**: Use `terraform/shared_resources/` for cross-cutting GCP resources.
- **File Manifest**: Specific list of files to create/edit.
- **Documentation Task**: Plan at least one `.md` file in `docs/`.

## 2. Issue Management (Part A & B)
Every deployable feature MUST be split:
- **Part A (Stage 1 - Prototyping)**: Logic, scripts, and notebook verification.
- **Part B (Stage 2 - Deployment)**: Terraform codification and Cloud Build triggers.
- **Dependency**: Part B issues must depend on Part A issues.

### Issue Proposal Table
Before creation, present:
| Issue to Create | Rationale | Scope | Stage | Dependency | DoD | Milestone |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |

## 3. High-Fidelity GitHub Issues
Every issue description MUST follow the strict template below. **MANDATORY**: Each issue must contain sufficient technical specifications, data schemas, and constraints to allow a senior developer to execute the task WITHOUT further clarification.

### Issue Template
> **User Story**
> - **As a** [persona]
> - **I want to** [action]
> - **So that** [value/benefit]
>
> ## Technical Specifications & Constraints
> - [Identify Scopes, Schemas, Algorithms, or GCP Services]
>
> ## Acceptance Criteria
> - [ ] Criterion 1
> - [ ] [Measurable goal 2]
>
> ## Definition of Done (DoD)
> - [ ] Code reviewed, linted, and tests passed.
> - [ ] **Documentation markdown file finalized and committed.**
>
> ## Dependent Issues
> - #IssueID

## 4. Documentation Standard
- Create/update files like `docs/modules/<name>.md`.
- Reference: `@.agents/rules/architecture-guide.md` for foundational principles.
