---
description: Creates a new skill from scratch. Use when a new domain needs a skill.
---

# /create-skill -- Create a New Skill from Scratch

**Argument hint:** `<skill name or domain to create a skill for>`

---

## Philosophy

A skill encodes *thinking*, not tool usage. The agent is already smart -- a skill provides the domain knowledge, institutional conventions, and hard-won patterns that no model fully possesses. Every skill should work with any agent, any framework, any era.

---

## Workflow

### Step 1: Understand the Skill

Gather concrete understanding of the skill's purpose. Ask the user:

- **What capability does this skill provide?** What can an agent do after reading this skill that it couldn't before?
- **When should an agent use this skill?** What are the triggers -- the situations, keywords, or user requests that should activate this skill?
- **What does the agent NOT already know?** What domain knowledge, institutional conventions, or hard-won patterns does this skill encode?
- **What are the inputs and outputs?** What does the skill start with, and what does it produce?

Ask 1-2 questions at a time. Conclude when you have a clear picture of the skill's purpose and scope.

**Skip this step only when** the skill's usage patterns are already clearly understood from the user's initial request.

### Step 2: Plan Reusable Contents

Determine what the skill needs beyond SKILL.md:

| Resource Type | When to Include | Example |
|---|---|---|
| `templates/` | Skill produces structured outputs | Process example template, report template |
| `references/` | Skill relies on external knowledge | API schemas, style guides, catalogs |
| `scripts/` | Skill involves executable steps | Validation scripts, scaffolding scripts |
| `examples/` | Skill benefits from real-world walkthroughs | Process example documents |

**Decision:** If no supporting files are needed, the skill is SKILL.md-only. This is fine -- many good skills are.

### Step 3: Initialize

Create the skill directory and SKILL.md with YAML frontmatter:

```
skills/[skill-name]/
+-- SKILL.md
+-- templates/    (if needed)
+-- references/   (if needed)
+-- scripts/      (if needed)
+-- examples/     (if needed)
```

The SKILL.md must start with:

```yaml
---
name: [skill-name]
description: >
  [Comprehensive description with trigger words and use cases.
   Include when to use AND when not to use.]
---
```

**Naming convention:** Use `verb-object` pattern (e.g., `release-specification`, `audit-skill-ecosystem`). If the skill is a process noun, use a descriptive compound (e.g., `skill-creation`, `process-extraction`).

### Step 4: Write the SKILL.md Body

Include these sections, in order:

1. **Philosophy** (Section I) -- Why this skill exists, what principle it encodes. Not just "what" but "why." 2-3 paragraphs.

2. **When to Use** (Section II) -- Trigger scenarios. Be specific and generous with examples. **Minimum 5 concrete scenarios.** Include "when NOT to use" if the skill could be misapplied.

3. **Workflow** (Section III) -- Step-by-step, numbered. Each step has:
   - A goal
   - Actions to take
   - Outputs produced
   - Key insights or decision points
   **Minimum 3 steps** with clear decision points.

4. **Best Practices** (Section IV) -- Actionable wisdom with rationale. Each practice explains *why*, not just *what*.

5. **Quality Checklist** (Section V) -- Binary yes/no verification questions. 5-10 items.

6. **Common Pitfalls** (Section VI) -- What goes wrong and how to avoid it. **Minimum 2 pitfalls** with problem/solution pairs.

7. **Example** (Section VII, recommended) -- A concrete walkthrough showing the skill in action on a real scenario.

8. **Related Skills** (Section VIII, optional) -- Links to complementary skills in the ecosystem.

### Step 5: Create Supporting Files

If templates, references, scripts, or examples were planned in Step 2, create them now. Test any scripts to verify they work.

### Step 6: Deliver and Iterate

Present the completed skill to the user. Ask:

> "Does this capture the pattern accurately? What's missing? Is there anything in the workflow that doesn't match how you actually do this?"

Highlight any assumptions you made that should be verified.

---

## Quality Gate

Before delivering, verify every item passes:

- [ ] **Trigger description covers at least 5 concrete scenarios**
- [ ] **Workflow has 3+ numbered steps with clear decision points**
- [ ] **Quality checklist has 5+ items**
- [ ] **At least 2 common pitfalls documented**
- [ ] **Philosophy section explains the "why," not just the "what"**
- [ ] **YAML frontmatter has both `name` and `description` fields**
- [ ] **Description includes trigger words for when to use the skill**
- [ ] **No references to specific agents or tools** -- patterns are tool-agnostic
- [ ] **Skill name follows verb-object or descriptive compound convention**
- [ ] **SKILL.md is under 500 lines** (move overflow to references/)

If **any check fails**, fix it before delivering. Do not deliver incomplete skills.

---

## Output

The completed skill directory saved at:

```
skills/[skill-name]/SKILL.md
```

Plus any supporting files in `templates/`, `references/`, `scripts/`, or `examples/`.
