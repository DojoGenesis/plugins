---
description: Turns a completed workflow into a reusable skill. Use when capturing a process you just ran.
---

# /process-to-skill -- Transform a Completed Workflow into a Reusable Skill

**Argument hint:** `<describe the process you want to capture, or point to a transcript/log>`

---

## Philosophy

We often develop valuable, multi-step processes for complex tasks. These processes are implicit knowledge -- a sequence of actions that leads to a high-quality outcome. This command makes that implicit knowledge explicit, transforming a one-off process into a repeatable practice that any agent can execute.

The proof is in the process example. Before abstracting into a skill, we document exactly what happened. The example is the anchor that keeps the skill honest.

---

## Workflow

### Step 1: Identify and Document the Process

Ask the user to describe or provide a transcript of a successful workflow they've run. Create a process example document using this template:

```markdown
# Process Example: [Name]

**Date:** [date]
**Context:** [when/why this process was used]
**Input:** [what the process started with]
**Output:** [what the process produced]

## Steps Taken

1. **[Step Name]**
   - **Goal:** [what this step aimed to accomplish]
   - **Actions:** [what was actually done]
   - **Tools/Techniques:** [what was used]
   - **Output:** [what this step produced]

2. [Step 2...]

## Key Decisions

- **[Decision 1]:** [what was decided, why, what alternatives were considered]

## What Worked

- [Success factor 1 -- why it worked]

## What Was Hard

- [Challenge 1 -- how it was resolved]

## Reusable Pattern

[The generalizable principle from this process -- the kernel that becomes the skill]
```

**Be detailed.** For each step, document the goal, actions taken, tools used, inputs, and outputs. The more specific the process example, the better the resulting skill.

Save as `docs/examples/[YYYY-MM-DD]_[process-name].md`.

### Step 2: Convert to Skill

Using the process example as raw material, extract the reusable pattern and structure it as a skill:

| Process Example Section | Skill Section |
|---|---|
| Context + Reusable Pattern | **I. Philosophy** |
| Steps Taken | **III. Workflow** (generalized) |
| What Worked | **IV. Best Practices** |
| What Was Hard | **VI. Common Pitfalls** |
| Key Decisions | Decision points within **III. Workflow** |

Use the `/create-skill` workflow (Steps 3-5) to build the SKILL.md from these extracted components.

**Critical transformation:** Generalize the specific process into a pattern. Replace specific file names with placeholders. Replace specific tools with generic descriptions. Keep the structure and reasoning, drop the implementation details.

### Step 3: Refine

Compare the skill back to the process example:

- Does the skill capture everything that made the process work?
- Is anything lost in generalization?
- Would someone following the skill make the same key decisions?
- Are the hard parts (from "What Was Hard") addressed in the workflow or pitfalls?

If gaps exist, update the skill. The process example is the truth -- the skill must honor it.

### Step 4: Validate

Ask the final validation question:

> "If a new agent encountered [the original situation], would this skill guide them to the same quality outcome?"

If the answer is "no" or "maybe," identify what's missing and return to Step 3.

If the answer is "yes," the skill is ready.

---

## Quality Gate

Before delivering, verify:

- [ ] **Process example document exists** with all template sections filled
- [ ] **Skill was derived from the process example**, not invented independently
- [ ] **Key decisions from the process are reflected** in the skill's workflow
- [ ] **Challenges from "What Was Hard" appear** in the skill's pitfalls
- [ ] **The generalization preserves the reasoning**, not just the steps
- [ ] **The validation question was asked and answered "yes"**
- [ ] **Both the process example and skill are saved** to appropriate locations

---

## Output

Two artifacts:

1. **Process example:** `docs/examples/[YYYY-MM-DD]_[process-name].md`
2. **Skill:** `skills/[skill-name]/SKILL.md` (created via `/create-skill` workflow)
