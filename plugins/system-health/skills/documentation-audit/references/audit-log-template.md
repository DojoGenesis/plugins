# Documentation Audit Log Template

Use this template when creating a new audit log file (e.g., `docs/audits/YYYY-MM-DD_documentation_audit.md`).

```markdown
# Documentation Audit: [Project Name]

**Date:** [YYYY-MM-DD]
**Auditor:** [Your Name]
**Scope:** [e.g., Full repository audit]

---

## Audit Findings

| File | Line(s) | Issue | Severity | Action Taken |
| :--- | :--- | :--- | :--- | :--- |
| `README.md` | 25-30 | The installation instructions are outdated and refer to a deprecated package. | High | Updated instructions in PR #123. |
| `docs/ARCHITECTURE.md` | 45 | The diagram does not include the new caching service. | Medium | Created issue #124 to update the diagram. |
| `CONTRIBUTING.md` | - | The link to the code of conduct is broken. | High | Fixed link in PR #125. |
| `SKILLS/retrospective.md` | 15 | A typo in the philosophy section. | Low | Corrected typo in PR #126. |

---

## Summary

- **Total Issues Found:** [Number]
- **Issues Resolved:** [Number]
- **New Issues Created:** [Number]

[A brief summary of the overall health of the documentation and any recurring themes that were identified.]
```

## Severity Definitions

| Severity | Meaning |
| :--- | :--- |
| **High** | Blocks onboarding, causes incorrect behavior, or contains broken links critical to usage. |
| **Medium** | Significant inaccuracy or outdated content that causes confusion but does not block basic usage. |
| **Low** | Minor issues: typos, style inconsistencies, non-critical outdated references. |
