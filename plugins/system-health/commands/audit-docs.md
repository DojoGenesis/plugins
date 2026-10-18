---
description: Audit documentation for drift.
---

# /audit-docs -- Audit Documentation for Drift

**Argument hint:** `<repository or documentation path>`

---

## Philosophy

Project documentation is a garden. When tended with care, it is a source of clarity and shared understanding. When neglected, it becomes overgrown with outdated information, broken links, and misleading instructions -- a phenomenon known as **documentation drift**. This drift erodes trust and creates confusion. The documentation audit is the practice of tending the garden: walking through documentation, pulling the weeds of inaccuracy, and pruning the branches of irrelevance.

---

## Workflow

### Step 1: Inventory All Documentation

**Goal:** Identify every document that needs auditing.

Locate and list all documentation in the repository:
- `README.md`
- API documentation (OpenAPI specs, route docs, etc.)
- Architecture documentation (ARCHITECTURE.md, design docs)
- Inline code comments and docstrings
- `CHANGELOG.md`
- `STATUS.md`
- `CONTRIBUTING.md`
- Guides, tutorials, and how-to documents in `docs/`
- Configuration documentation

### Step 2: Cross-Reference Against the Codebase

**Goal:** Compare what docs say against what the code actually does.

For each document, systematically check:

| Check | What to Compare |
|---|---|
| **API accuracy** | Do documented endpoints match actual routes/handlers? |
| **Type accuracy** | Do documented types/interfaces match actual definitions? |
| **Workflow accuracy** | Do documented workflows match actual code paths? |
| **Dependency accuracy** | Are documented dependencies current with lockfile/manifest? |
| **Configuration accuracy** | Do documented env vars/configs match actual usage? |
| **Example accuracy** | Do code examples actually run? |

### Step 3: Categorize Findings

**Goal:** Classify every finding into one of 4 categories.

| Category | Definition | Action |
|---|---|---|
| **Accurate** | Docs match code. No issues. | None |
| **Drifted** | Docs are outdated but partially correct. The feature exists but details are wrong. | Update the documentation |
| **Missing** | Code has functionality with no corresponding documentation. | Write new documentation |
| **Orphaned** | Docs describe something that no longer exists in the codebase. | Remove or archive the documentation |

### Step 4: Produce Correction Tasks

**Goal:** Generate actionable tasks for every drifted, missing, or orphaned item.

For each finding, produce:

| Field | Description |
|---|---|
| **File** | The documentation file affected |
| **Line(s)** | Specific line numbers if applicable |
| **Issue** | What is wrong |
| **Category** | Drifted / Missing / Orphaned |
| **Severity** | High (misleading), Medium (incomplete), Low (cosmetic) |
| **Correction** | What to change, with specifics |

### Step 5: Produce Audit Report

**Goal:** Create a permanent, dated audit artifact.

Save as `docs/audits/[YYYY-MM-DD]_documentation_audit.md` with:

1. **Summary** -- Total documents reviewed, issues by category, overall documentation health (GREEN/YELLOW/RED).
2. **Findings Table** -- All findings with file, lines, issue, category, severity, and action taken.
3. **Correction Tasks** -- Prioritized list of remaining fixes.
4. **Documentation Health by Area** -- Rate each documentation area (README, API docs, architecture docs, inline docs) with GREEN/YELLOW/RED.

---

## Quality Gate

Before delivering, verify:

- [ ] Every document in the repository was inventoried
- [ ] Docs were cross-referenced against actual code, not just read in isolation
- [ ] Every finding is categorized as Accurate, Drifted, Missing, or Orphaned
- [ ] Severity is assigned to every non-accurate finding
- [ ] Correction tasks have specific file paths and descriptions
- [ ] The audit report is saved as a dated file in `docs/audits/`
- [ ] Overall documentation health uses GREEN/YELLOW/RED classification

---

## Output

```
docs/audits/[YYYY-MM-DD]_documentation_audit.md
```
