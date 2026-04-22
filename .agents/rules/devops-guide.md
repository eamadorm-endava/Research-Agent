---
trigger: always_on
glob: "**/*.{yaml,yml,tf,tfvars,Makefile}"
description: "DevOps standards for GCP: Cloud Build pipelines, Terraform (CFF), and state management."
---

# devops-guide.md

Follow these protocols for Infrastructure as Code (IaC) and CI/CD orchestration:

### Provider & Infrastructure
- **Cloud Provider**: Exclusively use **Google Cloud Platform (GCP)**.
- **Terraform Standard**: 
  - Use [Cloud Foundation Fabric (CFF)](https://github.com/GoogleCloudPlatform/cloud-foundation-fabric) modules for all resources.
  - Prioritize Terraform over `gcloud` commands for resource provisioning.
- **State Management**:
  - Store state in a GCS bucket named: `<gcp-project-id>-tf-states`.
  - **Structure**: `/tfstates/<deployment_name>/tf.state`.

### CI/CD Pipelines (Cloud Build)
- **Tooling**: Use **Cloud Build**. Triggers must be created/managed via the centralized `terraform/scripts/cicd_triggers_creation.sh` script, **never** via Terraform.

### Automation & Execution
- **Makefile**: There must be **ONLY ONE Makefile** at the root of the repository to orchestrate all local and CI/CD tasks.
- **Workflow**: For all Stage 2 deployment tasks, Terraform codification, and CI/CD trigger management, you MUST trigger the specialized skill:
  - **Skill**: `@.agents/skills/deployment/SKILL.md`

### References
- `@.agents/rules/development-guide.md` for lifecycle definitions.
