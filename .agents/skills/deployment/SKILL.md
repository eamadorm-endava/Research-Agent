---
name: deployment
description: Manages Stage 2 (Deployment), including Terraform codification via CFF, CI/CD trigger management, and Cloud Build orchestration. Trigger this skill when promoting logic from prototyping to production.
---

# Deployment Skill

This skill governs the infrastructure codification and pipeline automation for the Research-Agent project, following Stage 2 of `@.agents/rules/development-guide.md`.

## 1. Terraform Codification (CFF)
`terraform/<deployable_name>_resources/`
- **Modules**: Exclusively use **Cloud Foundation Fabric (CFF)** modules.
- **Validation**: Ensure all resources (GCS, BQ, etc.) match the logic approved in the Stage 1 Notebook.

## 2. CI/CD Triggers
All Cloud Build triggers must be created/updated via the centralized script:
`terraform/scripts/cicd_triggers_creation.sh`.
- **RULE**: Cloud Build triggers must **NEVER** be managed via Terraform. 
- Triggers must be functional and tested before merging.

## 3. Definition of Done (DoD)
- Terraform modules applied successfully.
- CI/CD triggers functional (tested via `cicd_triggers_creation.sh`).
- PR merged into `main`.

## 4. Automation (Makefile)
- Ensure all common activities (pan, deploy, lint) are wrapped in the root `Makefile`.
- Context: Docker context should be the deployable root (e.g., `backend/name/`).

## References
- `@.agents/rules/development-guide.md` for lifecycle definitions.
- `@.agents/rules/devops-guide.md` for GCP and state management standards.
