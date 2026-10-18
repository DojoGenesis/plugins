---
description: Runs maintenance on an existing skill. Use when a skill is stale or broken.
---

# /maintain-skills -- Run Maintenance on an Existing Skill

**Argument hint:** `<skill path or name to maintain>`

---

## Philosophy

A skills directory is a living knowledge base. Without systematic maintenance, skills degrade: descriptions drift from reality, workflows become outdated, cross-references break, and terminology becomes inconsistent. Maintenance is not fixing what's broken -- it's keeping what works working well.

---

## Workflow

### Step 1: Read the Current Skill

Read the SKILL.md completely. Understand what the skill does, not just what it says.

Read any supporting files (templates, references, examples) to understand the full scope.

### Step 2: Check Accuracy

Is everything in the skill still true?

- Have conventions changed since the skill was written?
- Are referenced tools, APIs, or patterns still current?
- Do examples still represent real, valid scenarios?
- Has the domain itself evolved?

**Flag** anything that is outdated, incorrect, or misleading.

### Step 3: Check Completeness

Is anything missing that should be there?

- Are there new trigger scenarios the skill should cover?
- Are there new pitfalls discovered through real usage?
- Are there new best practices that have emerged?
- Should the skill reference new related skills?

**Flag** any gaps.

### Step 4: Check Triggers

Would a new agent recognize when to use this skill from the YAML description alone?

- Does the description include enough trigger words?
- Are at least 5 concrete scenarios listed in "When to Use"?
- Is "When NOT to Use" covered if the skill could be misapplied?

**Flag** if the description is too vague or narrow.

### Step 5: Check Workflow

Are the steps still in the right order?

- Should any steps be added?
- Should any steps be removed?
- Should any steps be reordered?
- Are decision points clearly marked?
- Do outputs from each step feed logically into the next?

**Flag** any workflow issues.

### Step 6: Check Quality Checklist

Are the quality criteria still relevant?

- Do all checklist items still apply?
- Are there new criteria that should be added?
- Do the criteria match the current workflow?

**Flag** any outdated or missing criteria.

### Step 7: Check Supporting Files

Are templates, references, and examples up to date?

- Do templates match the current workflow?
- Are references still valid and accessible?
- Do examples still demonstrate the skill accurately?

**Flag** any outdated supporting files.

### Step 8: Apply Changes and Version Bump

If changes are non-trivial:

1. Apply all flagged changes to SKILL.md and supporting files
2. Update the version (e.g., v1.0 to v1.1)
3. Update "Last Updated" date
4. Use verb-object naming if renaming is needed

If changes are trivial (typos, formatting): fix without version bump.

### Step 9: Produce Maintenance Report

Create a report documenting:

```markdown
# Maintenance Report: [skill-name]

**Date:** [date]
**Previous Version:** [version]
**New Version:** [version]

## What Was Checked

| Dimension | Status | Notes |
|---|---|---|
| Accuracy | Pass/Flagged | [notes] |
| Completeness | Pass/Flagged | [notes] |
| Triggers | Pass/Flagged | [notes] |
| Workflow | Pass/Flagged | [notes] |
| Quality Checklist | Pass/Flagged | [notes] |
| Supporting Files | Pass/Flagged | [notes] |

## Changes Made

- [Change 1]
- [Change 2]

## Current Grade

**[A+ / A / B / C / D / F]**

### Grading Rubric

- **A+:** Complete philosophy, workflow, checklist, pitfalls, supporting files, process example
- **A:** Complete philosophy, workflow, checklist, pitfalls
- **B:** Has workflow and checklist, missing philosophy or pitfalls
- **C:** Has workflow but missing checklist, pitfalls, or philosophy
- **D:** Incomplete workflow
- **F:** Stub or non-functional
```

Save as `docs/maintenance/[YYYY-MM-DD]_[skill-name]_maintenance.md`.

---

## Quality Gate

Before completing maintenance:

- [ ] **All 9 dimensions were checked**, not a subset
- [ ] **Every flagged issue was either fixed or documented** with a rationale for deferral
- [ ] **Version was bumped** if changes were non-trivial
- [ ] **Maintenance report was created** with grade
- [ ] **No broken cross-references** remain after changes

---

## Output

1. **Updated skill:** `skills/[skill-name]/SKILL.md` (if changes were made)
2. **Maintenance report:** `docs/maintenance/[YYYY-MM-DD]_[skill-name]_maintenance.md`
