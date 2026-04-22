---
name: security-audit
description: Conducts security audits, classifies risks (Urgent/High/Medium/Low), and generates the cybersec_report.md artifact. Trigger this skill during the Stage 1 implementation cycle.
---

# Security Audit Skill

This skill governs the vulnerability assessment and threat reporting for the Research-Agent project, ensuring compliance with the thresholds defined in `@.agents/rules/development-guide.md`.

## 1. Threat Detection logic
Analyze the task's code changes for vulnerabilities (e.g., hardcoded secrets, insecure API usage, overly permissive IAM).

## 2. Report Generation
Generate a `cybersec_report.md` at the root using this template:

### Vulnerability Report
| Risk Level | File(s) | Rationale | Possible Fix |
| :--- | :--- | :--- | :--- |
| **Urgent** | | | |
| **High** | | | |
| **Medium** | | | |
| **Low** | | | |

## 3. Remediation Loop
- **Zero Tolerance**: You MUST eliminate all **High** and **Urgent** threats.
- **Minimization**: You MUST minimize **Medium** risks to a **maximum of 2** before finalizing logic.
- **Automation**: Automatically update the code until the skill reports a safe state according to these thresholds.

## References
- `@.agents/rules/development-guide.md` for lifecycle thresholds.
- `@.agents/rules/cybersecurity-guide.md` for secret hygiene and ADC standards.
