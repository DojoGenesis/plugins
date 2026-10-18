---
description: Compress a session into lasting wisdom artifacts.
---

# /compress -- Compress a Session into Potent Wisdom Artifacts

**Argument hint:** `<session to compress -- paste transcript, or describe what happened>`

---

## Philosophy

An agent's context window is like a garden's growing season -- finite and precious. To fill it with raw, unprocessed history is to invite weeds. The compression ritual is the **Art of Letting Go** -- a conscious practice of choosing what is essential to cultivate and what can be respectfully composted.

This is not an act of uprooting, but of distillation. We transform the raw material of conversation into refined artifacts of wisdom: philosophical reflections, key decisions, and reusable seeds. Compression ensures that our garden remains potent and relevant -- a source of clarity, not noise.

---

## Workflow

### Step 1: Signal Intent

Announce the compression ritual. This frames the activity as deliberate and mindful:

> "We're entering a compression ritual. The goal is to distill this session into its essential wisdom -- cultivating what matters and composting what doesn't."

### Step 2: Review the Material

Accept the session material in any form:

- **Pasted transcript** -- Review it directly
- **Uploaded file** -- Read and analyze
- **Description of what happened** -- Ask clarifying questions to surface key moments
- **If ~~chat is connected** -- Pull recent threads from the relevant time period

Read through the material with a specific intention: to identify the moments of significance. Look for:

- **Key Decisions** -- Moments where a choice was made that altered direction
- **Profound Insights** -- "Aha!" moments, new understandings, or philosophical reflections
- **Actionable Learnings** -- Concrete lessons that should inform future behavior
- **Reusable Patterns** -- Ideas or workflows that could be generalized into seeds
- **Unresolved Questions** -- Important questions raised but not yet answered
- **Failures and Dead Ends** -- What didn't work and why (often the most valuable wisdom)

### Step 3: Choose the Right Vessel

For each insight worth preserving, select the appropriate artifact type:

| Artifact Type | When to Use | Output Location |
|---|---|---|
| **Philosophical Reflection** | Deep insight about how to think or work | `artifacts/YYYY-MM-DD_reflection_[name].md` |
| **Conversation Summary** | Key decisions, context, and outcomes from a discussion | `artifacts/YYYY-MM-DD_summary_[name].md` |
| **Seed** | A reusable pattern (formalize with `/plant`) | `seeds/YYYY-MM-DD_[seed-name].md` |
| **Documentation Update** | Something that should be added to existing docs | Direct edit to target file |
| **Decision Record** | A specific decision with rationale and alternatives considered | `artifacts/YYYY-MM-DD_decision_[name].md` |

### Step 4: Write Each Artifact

Write each artifact using the appropriate template. Write with the intention of distillation -- capture the essence, not the raw transcript. Link between artifacts where appropriate.

**For Philosophical Reflections:**
```markdown
# Reflection: [Title]

**Distilled:** YYYY-MM-DD
**Origin:** [Session or context]
**Tier:** B (Curated Wisdom)
**Type:** reflection

---

[2-4 paragraphs capturing the insight, why it matters, and how it changes thinking]
```

**For Conversation Summaries:**
```markdown
# Summary: [Title]

**Distilled:** YYYY-MM-DD
**Origin:** [Session description]
**Duration:** [Approximate time]
**Tier:** B (Curated Wisdom)
**Type:** summary

---

## Key Decisions
- [Decision 1: what was decided and why]
- [Decision 2: what was decided and why]

## Outcomes
- [What was produced or accomplished]

## Open Questions
- [Unresolved items to carry forward]
```

**For Decision Records:**
```markdown
# Decision: [Title]

**Recorded:** YYYY-MM-DD
**Context:** [What led to this decision]
**Tier:** B (Curated Wisdom)
**Type:** decision

---

## Options Considered
1. [Option A] -- [Pros/Cons]
2. [Option B] -- [Pros/Cons]

## Chosen
[Selected option]

## Rationale
[Why this was the best choice given the constraints]

## Revisit Trigger
[When or why to reconsider this decision]
```

**For Seeds:** Use `/plant` to formalize, or write inline using the seed template from the plant command.

### Step 5: Apply the 3-Month Rule

For **every** potential artifact, explicitly evaluate:

| Category | Action | Examples |
|---|---|---|
| **CULTIVATE** | Preserve as Tier B artifact | Decisions, insights, seeds, failures, breakthroughs, architectural changes |
| **SUMMARIZE** | Condense to 1-2 sentences | Activities, discussions, exploration paths, intermediate steps |
| **COMPOST** | Release with gratitude | Pleasantries, debugging dead-ends, repetitive iterations, context captured elsewhere |

Present this triage to the user:

> "Here's how I've applied the 3-month rule to this session:"
> - **Cultivated (N items):** [list]
> - **Summarized (N items):** [list]
> - **Composted (N items):** [list]

### Step 6: Write the Compression Log

Every compression produces a meta-record documenting the distillation itself:

```markdown
# Compression Log: YYYY-MM-DD

**Source:** [Description of what was compressed]
**Original volume:** ~[X] tokens (estimated)
**Compressed volume:** ~[Y] tokens
**Compression ratio:** [Z]% reduction

---

## Artifacts Cultivated

| Type | Path | Description |
|---|---|---|
| [Type] | `[path]` | [Brief description] |

## Insights Preserved

- [Key insight 1]
- [Key insight 2]

## Context Composted

- [What was released and why]

## Seeds Planted

- [Seed name]: [Brief pattern description]
```

Save the compression log to: `compressions/YYYY-MM-DD_compression_log.md`

### Step 7: Suggest Tier Placement

For each artifact, recommend tier placement:

- **Tier A (Raw, 1-3 day lifespan):** Daily notes, scratch observations, unverified ideas
- **Tier B (Curated, permanent):** Validated insights, decisions, seeds, reflections
- **Tier C (Compressed archive, read-only):** Monthly summaries, historical records

Most compression artifacts should land in **Tier B**. If a session produced mostly routine work, the compression log itself may be the only Tier B artifact, with everything else composted.

---

## Quality Gate

Before delivering, verify every item passes:

- [ ] **3-month rule explicitly applied** -- shows what was cultivated, summarized, and composted
- [ ] **Compression log produced** with volume metrics (original tokens > compressed tokens)
- [ ] **Every artifact has metadata** (type, tier, date)
- [ ] **Seeds identified and either planted or flagged** for later `/plant`
- [ ] **Growth language only** -- no "store," "retrieve," "create," or "delete"
- [ ] **Artifacts are significantly shorter** than the source material
- [ ] **Links between related artifacts** where appropriate

If **any check fails**, fix it before delivering.

---

## Output

All artifacts saved to their respective directories:

```
compressions/YYYY-MM-DD_compression_log.md
artifacts/YYYY-MM-DD_[type]_[name].md
seeds/YYYY-MM-DD_[seed-name].md  (if seeds were planted)
```
