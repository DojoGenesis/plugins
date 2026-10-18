---
description: Generate or update a STATUS.md.
---

# /status-report -- Generate a Project STATUS.md

**Argument hint:** `<project name or path>`

---

## Philosophy

A STATUS.md file is a ritual of bearing witness -- a practice of radical honesty about where a project truly is. Not where we wish it were, or where it is supposed to be. It provides a single, trusted source of truth that grounds conversations and decisions in reality. It is a dashboard, not a novel.

---

## Workflow

### Step 1: Gather Context

**Goal:** Collect current project state from all available sources.

1. **If `~~repository` is connected:** Read recent commits, open pull requests, CI status, and branch activity.
2. **If `~~project tracker` is connected:** Pull sprint progress, active issues, and upcoming milestones.
3. **If neither is connected:** Read the local codebase, git log, and any existing STATUS.md for context.
4. **Check for prior audits:** Look in `docs/audits/` for the most recent health audit and behavioral architecture map.

### Step 2: Write STATUS.md

**Goal:** Produce a concise, honest status document.

Write STATUS.md at the project root with the following sections:

#### Section 1: Current State

A one-paragraph summary of where the project stands right now. Be honest and specific.

#### Section 2: Recent Progress

What happened in the last 1-2 weeks. Bullet points, not paragraphs. Include:
- Features shipped
- Bugs fixed
- Infrastructure improvements
- Documentation updates

#### Section 3: Behavioral Architecture

An abbreviated semantic cluster summary. If a `/map-system` output exists, reference it. Otherwise, provide a brief list of the project's main capabilities as verb clusters.

#### Section 4: Health Dashboard

Rate 5 dimensions using the health audit framework:

| Dimension | Status | Notes |
|---|---|---|
| Critical Issues | [GREEN/YELLOW/RED] | [one-line summary] |
| Security | [GREEN/YELLOW/RED] | [one-line summary] |
| Testing | [GREEN/YELLOW/RED] | [one-line summary] |
| Technical Debt | [GREEN/YELLOW/RED] | [one-line summary] |
| Documentation | [GREEN/YELLOW/RED] | [one-line summary] |

If a recent `/health-audit` exists, use those results. Otherwise, do a quick assessment.

#### Section 5: Active Risks

What could go wrong. Be ruthlessly honest about:
- Technical risks (fragile code, missing tests, security gaps)
- Process risks (blocked dependencies, unclear ownership)
- External risks (third-party service changes, API deprecations)

#### Section 6: Next Milestones

Upcoming deliverables with dates (if known). Be specific about what "done" looks like for each.

### Step 3: Save

Save as `STATUS.md` at the project root. If a previous STATUS.md exists, overwrite it -- status documents are living documents, not historical records (that's what `docs/audits/` is for).

---

## Quality Gate

Before delivering, verify:

- [ ] Current State section is honest and specific, not aspirational
- [ ] Recent Progress covers the last 1-2 weeks with concrete items
- [ ] Health Dashboard uses GREEN/YELLOW/RED for all 5 dimensions
- [ ] Active Risks section exists and is not empty
- [ ] Next Milestones are specific with measurable "done" criteria
- [ ] STATUS.md is concise -- a dashboard, not a novel
- [ ] If prior audits exist, they are referenced rather than duplicated

---

## Output

```
STATUS.md (at project root)
```
