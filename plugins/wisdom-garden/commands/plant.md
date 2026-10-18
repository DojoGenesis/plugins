---
description: Plant a seed from an experience or insight.
---

# /plant -- Plant a Seed from an Experience or Insight

**Argument hint:** `<insight, learning, or experience to capture>`

---

## Philosophy

Every experience contains seeds -- reusable patterns waiting to be extracted and cultivated. The practice is learning to see them, name them, and plant them where they'll grow. A seed planted today compounds: it becomes a skill next month, a plugin next quarter, and eventually part of your institutional DNA.

Seeds use growth language: they are "planted," "cultivated," and "harvested" -- never "created," "stored," or "retrieved."

---

## Workflow

### Step 1: Gather the Raw Material

Ask the user what they learned, discovered, or experienced. Accept any of:

- A lesson from a project
- A pattern they noticed across multiple situations
- A mistake they made and what it taught them
- A technique or approach that worked surprisingly well
- A reframe that changed how they think about a problem
- A decision framework that proved useful

If the user provides a brief description, ask follow-up questions to uncover the deeper pattern. The goal is to move from the specific experience to the reusable principle underneath.

**Skip this step only when** the user's initial input already contains a clear pattern with context.

### Step 2: Articulate the Seed

Help the user shape their insight into a structured seed with all 6 fields:

| Field | Purpose | Guidance |
|---|---|---|
| **Name** | Short, memorable identifier | Use verb-object or descriptive compound format (e.g., "backend-grounding-first," "the-reframe-is-the-prize," "parallel-tracks") |
| **Context** | When and where this insight emerged | Specific project, session, or situation -- ground it in reality |
| **Pattern** | The reusable principle | Generalize beyond the specific experience. Ask: "If someone else faced a similar situation, what would the advice be?" |
| **Trigger** | When to apply this seed in the future | Be specific: what signals, keywords, or situations should remind someone of this seed? |
| **Anti-pattern** | What the opposite looks like | Describe what happens when someone ignores this seed. This sharpens the pattern by contrast. |
| **Example** | The specific experience that birthed the seed | The concrete story that proves the pattern is real, not theoretical |

**Key Insight:** The generalization step (Context > Pattern) is where most value is created. Push the user to abstract from "what happened" to "what this means for similar situations."

### Step 3: Check for Existing Seeds

If **~~knowledge base** is connected:
1. Search for existing seeds with similar patterns, triggers, or names
2. If a similar seed exists, present it and ask: "This existing seed covers similar ground. Should we merge, differentiate, or plant yours as a new seed?"
3. If no similar seed exists, proceed to planting

If **~~knowledge base** is not connected:
- Skip this step and proceed to planting

### Step 4: Write the Seed Artifact

Write the seed as a structured markdown file with all 6 fields and metadata:

```markdown
# Seed: [Name]

**Planted:** YYYY-MM-DD
**Domain:** [area -- e.g., architecture, process, decision-making, collaboration]
**Tier:** B (Curated Wisdom)
**Type:** seed

---

## Pattern

[One to two sentences: the reusable principle, generalized beyond the specific experience]

## Context

[Where and when this insight emerged -- the specific situation that birthed it]

## Trigger

When to cultivate this seed:
- [Signal, situation, or keyword 1]
- [Signal, situation, or keyword 2]
- [Signal, situation, or keyword 3]

## Anti-pattern

What it looks like when this seed is ignored:
- [Consequence or symptom 1]
- [Consequence or symptom 2]

## Example

[The concrete experience that proves this pattern. Include what happened, what was decided, and what the outcome was.]

## Related Seeds

- [Seed that complements this one]
- [Seed that contrasts with this one]
```

### Step 5: Save and Confirm

Save the seed file to: `seeds/YYYY-MM-DD_[seed-name].md`

Present the completed seed to the user:

> "Here's the seed I've planted. Does the pattern capture the insight accurately? Is there anything in the trigger or anti-pattern that should be refined?"

---

## Quality Gate

Before delivering, verify every item passes:

- [ ] **Seed has all 6 fields** (Name, Context, Pattern, Trigger, Anti-pattern, Example)
- [ ] **Name follows verb-object or descriptive compound convention**
- [ ] **Pattern is generalized** beyond the specific experience (reusable, not one-time)
- [ ] **Trigger is specific** -- contains at least 2 concrete signals or situations
- [ ] **Anti-pattern sharpens the pattern** by showing what the opposite looks like
- [ ] **Example is grounded** in a real experience, not hypothetical
- [ ] **Metadata is complete** (type: seed, tier: B, planted date, domain)
- [ ] **Growth language only** -- no "store," "retrieve," "create," or "delete"

If **any check fails**, fix it before delivering. Do not plant incomplete seeds.

---

## Output

The completed seed saved at:

```
seeds/YYYY-MM-DD_[seed-name].md
```
