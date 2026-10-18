---
description: Audits the health of a whole skills ecosystem. Use when reviewing a skills directory.
---

# /audit-skills -- Audit the Health of an Entire Skills Ecosystem

**Argument hint:** `<skills directory path>`

---

## Philosophy

A skills ecosystem, like any knowledge base, degrades over time. New skills are created with high standards, but older skills may lack structure, examples, or ecosystem connections. Without regular audits, quality becomes inconsistent. This command is about proactive maintenance -- catching gaps early and keeping the entire ecosystem healthy.

---

## Workflow

### Step 1: Inventory

List every skill in the directory. For each skill, record:

| Field | How to Check |
|---|---|
| Name | Directory name |
| Version | From SKILL.md frontmatter or metadata |
| Description length | Character count of YAML `description` field |
| Has philosophy (Y/N) | Section I or "Philosophy" heading present |
| Has workflow (Y/N) | Section III or "Workflow" heading present |
| Has checklist (Y/N) | Section V or "Quality Checklist" heading present |
| Has pitfalls (Y/N) | Section VI/VII or "Pitfalls" heading present |
| Has example (Y/N) | Section with "Example" heading present |
| Line count | Total lines in SKILL.md |

Use file listing and content scanning to build this inventory. Do not read every skill in full at this stage -- use headers and line counts for the initial pass.

### Step 2: Grade Each Skill

Apply the grading rubric:

| Grade | Criteria |
|---|---|
| **A+** | Complete philosophy, workflow, checklist, pitfalls, supporting files, process example |
| **A** | Complete philosophy, workflow, checklist, pitfalls |
| **B** | Has workflow and checklist, missing philosophy or pitfalls |
| **C** | Has workflow but missing checklist, pitfalls, or philosophy |
| **D** | Incomplete workflow |
| **F** | Stub or non-functional |

For borderline cases, read the skill in full before assigning a grade.

### Step 3: Identify Patterns

Analyze the grade distribution. Look for systematic gaps:

- Do most skills lack philosophy sections? That's a systemic issue.
- Are pitfalls consistently missing? That's a pattern.
- Are newer skills better than older ones? That indicates improving practices.
- Are skills in one domain stronger than another? That indicates uneven investment.

Document the patterns -- they inform the upgrade strategy.

### Step 4: Prioritize Upgrades

Sort by **impact x effort**:

| Priority | Impact | Effort | Example |
|---|---|---|---|
| **High** | Frequently used, blocking workflows | Low-medium effort fix | D/C skills with clear gaps |
| **Medium** | Moderately used, structural issues | Medium effort | B skills needing philosophy or pitfalls |
| **Low** | Rarely used, minor enhancements | Any effort | A skills that could become A+ |

**Do not prioritize alphabetically.** Skills used most frequently should be upgraded first, regardless of their position in the list.

### Step 5: Produce Audit Report

Create a comprehensive report:

```markdown
# Skills Audit Report

**Date:** [date]
**Directory:** [path]
**Total Skills:** [count]

## Skills Inventory

| Skill | Grade | Philosophy | Workflow | Checklist | Pitfalls | Example | Lines |
|---|---|---|---|---|---|---|---|
| [name] | [grade] | Y/N | Y/N | Y/N | Y/N | Y/N | [count] |

## Grade Distribution

| Grade | Count | Percentage |
|---|---|---|
| A+ | [n] | [%] |
| A | [n] | [%] |
| B | [n] | [%] |
| C | [n] | [%] |
| D | [n] | [%] |
| F | [n] | [%] |

## Patterns Identified

- [Pattern 1]
- [Pattern 2]

## Top 5 Upgrade Recommendations

1. **[skill-name]** ([current grade] -> [target grade])
   - Gap: [what's missing]
   - Impact: [why this matters]
   - Effort: [estimated work]

2. [...]

## Ecosystem Health Verdict

**[Healthy / Needs Attention / Critical]**

- **Healthy:** 80%+ skills at A or A+, no D/F skills
- **Needs Attention:** 60-79% at A or A+, or any D/F skills exist
- **Critical:** <60% at A or A+, or multiple D/F skills
```

Save as `docs/audits/[YYYY-MM-DD]_skills_audit.md`.

---

## Quality Gate

Before completing the audit:

- [ ] **Every skill in the directory was inventoried**
- [ ] **Every skill received a grade** based on the rubric
- [ ] **Grade distribution was calculated**, not just a flat list
- [ ] **Patterns were identified** across the ecosystem
- [ ] **Upgrades were prioritized by impact x effort**, not alphabetically
- [ ] **Top 5 recommendations include** current grade, target grade, gap, impact, and effort
- [ ] **Ecosystem health verdict was assigned** using the defined thresholds

---

## Output

**Audit report:** `docs/audits/[YYYY-MM-DD]_skills_audit.md`
