### Vulnerability Report
| Risk Level | File(s) | Rationale | Possible Fix |
| :--- | :--- | :--- | :--- |
| **Urgent** | None | | |
| **High** | None | | |
| **Medium** | None | | |
| **Low** | `agent/core_agent/tools/kb_tools.py` | `EKB_PIPELINE_URL` is configurable via env vars. A malicious endpoint could receive the ID token. | Standard config risk; ensure only trusted URLs are set in environment. |
| **Low** | `agent/core_agent/tools/kb_tools.py` | High timeout (300s) might tie up resources if the downstream service is slow. | This is intentional for document processing, but could be tuned based on production performance. |
