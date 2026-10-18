---
description: Promotes a proven seed into a full skill. Use when a seed has earned skill status.
---

# /elevate-seed -- Promote a Proven Seed into a Full Skill

**Argument hint:** `<seed name or path>`

---

## Philosophy

A seed is a potent insight, a moment of clarity captured. A skill is an *instrument* -- that same insight transformed into a repeatable, structured process. Not every seed should become a skill. Only seeds that have proven their value through repeated application deserve this promotion. Patience is a virtue: premature elevation creates brittle skills.

---

## Workflow

### Step 1: Read and Verify the Seed

Read the seed completely. Verify it has the core components:

| Component | What to Look For |
|---|---|
| **Name** | Clear, descriptive name |
| **Context** | When/why this insight was captured |
| **Pattern** | The core insight or principle |
| **Trigger** | When this wisdom should be applied |
| **Anti-pattern** | What happens when this wisdom is ignored |
| **Example** | At least one concrete application |

If any component is missing, the seed is not ready for elevation. Document what's missing and advise the user to enrich the seed first.

### Step 2: Assess Readiness

Answer these questions:

1. **Has this seed been applied 2+ times?** Look for evidence of repeated use -- references in other documents, multiple examples, mentions in retrospectives.
2. **Is the pattern stable or still evolving?** If the seed's core insight has changed significantly between applications, it's still maturing.
3. **Does the seed describe a multi-step process?** Seeds that are purely philosophical reminders should remain seeds. Skills must be actionable.

**If NOT ready** (applied <2 times, pattern still evolving, or purely philosophical):

> "This seed has been applied [N] time(s) and the pattern appears to still be [evolving/stabilizing]. I recommend applying it in [1-2] more contexts before elevation. Specifically, try applying it to [suggested scenario] to test whether the pattern holds."

Stop here. Do not force-elevate an unripe seed.

**If ready:** Proceed to Step 3.

### Step 3: Convert Seed Components to Skill Sections

Map the seed's components to skill structure:

| Seed Component | Skill Section |
|---|---|
| **Pattern** (core insight) | **I. Philosophy** -- Expand the insight into the "why" behind the skill |
| **Trigger** | **II. When to Use** -- Expand into 5+ concrete scenarios |
| **Example(s)** | **VII. Example** -- Use as the basis for a process example document |
| **Anti-pattern** | **VI. Common Pitfalls** -- Transform into problem/solution pairs |

Add what the seed doesn't have:
- **III. Workflow** -- Generalize from the examples into numbered steps with decision points
- **IV. Best Practices** -- Extract wisdom from what worked across applications
- **V. Quality Checklist** -- Create binary verification criteria for the skill's output

### Step 4: Build the Skill

Use the `/create-skill` workflow (Steps 3-6) to create the full skill from the converted components:

1. Initialize the skill directory with SKILL.md
2. Write all sections (philosophy through related skills)
3. Create supporting files if needed (templates, examples)
4. Run the quality gate

### Step 5: Link Back to the Seed

In the skill's philosophy section, acknowledge the seed origin:

> "This skill was elevated from the seed '[seed-name],' which captured [the core insight]. Through [N] applications, the pattern proved stable enough to formalize into a repeatable process."

This preserves the lineage and honors the seed's contribution.

---

## Quality Gate

Before completing elevation:

- [ ] **Seed was read completely** and all components verified
- [ ] **Readiness was assessed** -- seed was applied 2+ times and pattern is stable
- [ ] **All seed components were mapped** to skill sections
- [ ] **Workflow section was added** (seeds don't have this -- you must create it)
- [ ] **Quality checklist was added** (seeds don't have this -- you must create it)
- [ ] **The resulting skill passes the `/create-skill` quality gate**
- [ ] **Seed origin is acknowledged** in the philosophy section

---

## Output

1. **Skill:** `skills/[skill-name]/SKILL.md` (created via `/create-skill` workflow)
2. **Process example** (optional): `docs/examples/[YYYY-MM-DD]_[seed-name]_elevation.md`
