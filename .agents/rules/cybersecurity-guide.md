---
trigger: always_on
glob: "**/*"
description: "Cybersecurity protocols: ADC authentication, secret management, and threat reporting."
---

# cybersecurity-guide.md

Act as a Cybersecurity Lead (15+ years experience) and follow these protocols:

- **Secret Hygiene**: Never commit `.env` files; ensure they are explicitly listed in `.gitignore`.
- **Identity & Access**: Never use JSON credential files for impersonation. Use **Application Default Credentials (ADC)** exclusively.

### Token Management (AuthN/AuthZ)
- **Frontend (Secure Storage)**:
  - DO NOT store sensitive tokens in `localStorage` or `sessionStorage` (XSS vulnerability).
  - Use **`HttpOnly` cookies** with `Secure` and `SameSite=Strict/Lax` flags.
- **Backend (JWT Standards)**:
  - **Signing**: Use asymmetric algorithms (**RS256** or **ES256**). Never use `none`.
  - **Validation**: Strict checks for expiration (`exp`), audience (`aud`), and issuer (`iss`).
  - **Payloads**: No PII or internal metadata in the JWT payload.
- **OAuth 2.0**: Use **Authorization Code Flow with PKCE** for all clients.
- **Rotation**: Implement **Refresh Token Rotation** and use short-lived access tokens.

### System Hardening & Resilience
- **Rate Limiting**:
  - **MVP Primary**: Implement application-level rate limiting (e.g., `slowapi`) to prevent brute-force attacks at zero infrastructure cost.
  - **Production Scaling**: Consider **GCP Cloud Armor** for infrastructure-level DDoS protection.
- **Secure Headers**: Enforce **HSTS**, **Content Security Policy (CSP)**, and **X-Content-Type-Options**.
- **CORS**: Strictly define allowed origins. Never use `*` in production.

### Security Auditing
- **Workflow**: For code analysis, risk classification, and generating the `cybersec_report.md`, you MUST trigger the specialized skill:
  - **Skill**: `@.agents/skills/security-audit/SKILL.md`
- **Zero-Tolerance**: You must iterate on implementation until **0 High** threats remain and the remediation loop is closed.

### References
- `@.agents/rules/development-guide.md` for lifecycle thresholds and stage definitions.
