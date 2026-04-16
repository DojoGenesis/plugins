---
name: adr-writer
version: "1.0.0"
model: sonnet
description: "Produces a numbered Architecture Decision Record with context analysis, route comparison, decision rationale, consequences, and propagation checklist. Use when: 'write an ADR', 'architectural decision', 'record a decision', 'ADR for'."
triggers:
  - "write an ADR"
  - "architectural decision"
  - "record a decision"
  - "ADR for"
category: dojo-craft

inputs:
  - name: decision_topic
    type: string
    description: The architectural decision or topic to document
    required: true
outputs:
  - name: adr_document
    type: ref
    format: markdown
    description: Numbered ADR markdown file saved to the decisions/ directory
---

# ADR Writer Skill

## I. Philosophy

An Architecture Decision Record is the project's institutional memory. Every significant technical choice that lives only in someone's head is a future incident — a re-fight, a regression, or a confused new contributor asking why things work the way they do.

ADRs are not bureaucracy. They are the minimum viable documentation that keeps a fast-moving project from looping back on itself. A good ADR takes fifteen minutes to write and saves three hours of re-derivation six months later.

The crafter does not write ADRs for every change — only for decisions that:
- Are hard to reverse
- Affect multiple components or repos
- Were made between competing legitimate alternatives
- Will confuse someone who wasn't in the room

## II. When to Use

- When a significant architectural choice is being made or was just made
- When two or more teams or components need to align on an approach
- When a previous decision is being revisited and the reason for the change should be recorded
- When a new contributor asks "why do we do X this way?" and the answer is not in the code

Do not write an ADR for trivial implementation choices, naming conventions, or decisions with only one viable option.

## III. Workflow

### Step 1: GATHER

Read the decision context before writing anything.

1. Identify what is being decided and why it matters now. What forces are at play — performance, maintainability, velocity, contract compatibility, cost?
2. Identify which repos, contracts, and interfaces are affected. Run `grep` and `glob` searches if needed — do not assume.
3. Identify who made or is making the decision. Note any external constraints (regulatory, contractual, hard deadlines) that eliminate certain routes.
4. Check whether a prior ADR covers related ground. Search the `decisions/` directory for existing ADR numbers and topics.

### Step 2: SCOUT

Generate 3-5 routes before selecting one.

For each route:
- **Description:** What does this approach actually do?
- **Risk:** What can go wrong? What is the blast radius if it fails?
- **Time:** Rough estimate to implement
- **Key tradeoff:** What does this route give up to get its benefits?

Do not present routes that are not genuinely distinct. If two routes differ only in implementation detail (same architectural approach, different library), collapse them.

Optionally invoke the `scout-writer` skill to produce a full scout document for complex decisions before drafting the ADR.

### Step 3: COMPARE

Build a comparison table.

| Route | Description | Risk | Time | Key Tradeoff |
|-------|-------------|------|------|-------------|
| A     | ...         | Low  | 2d   | ...         |
| B     | ...         | High | 1d   | ...         |
| C     | ...         | Med  | 3d   | ...         |

The table forces honest assessment. If you cannot fill in all four columns for a route, you do not understand it well enough to recommend it.

### Step 4: DECIDE

Select the route with explicit rationale.

State:
1. Which route was chosen
2. Why it was chosen (the decisive factors)
3. What was NOT chosen and why (this is the most valuable part — it prevents re-arguing the same ground)
4. Any conditions under which the decision should be revisited

### Step 5: PROPAGATE

Generate a propagation checklist — the list of documents, repos, and contracts that need to be updated as a consequence of this decision.

Examples:
- [ ] Update `CLAUDE.md` to reflect new convention
- [ ] Update Gateway route handler in `AgenticGatewayByDojoGenesis/server/`
- [ ] Notify CLI team of interface change
- [ ] Update port reference in `README.md`
- [ ] Create follow-up ADR if decision has a staged rollout

This checklist prevents the decision from landing in documentation but failing to propagate to the codebase.

### Step 6: WRITE

Produce the ADR using the canonical template:

```
# ADR-NNN: [Title]

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Superseded | Deprecated
**Affects:** [list of repos, components, or contracts]

## Context

[2-4 sentences describing the situation, forces at play, and why a decision is needed now. Not the decision — the context that forces a decision.]

## Routes Considered

[The comparison table from Step 3, plus a brief paragraph for each route expanding on its tradeoffs.]

## Decision

[One sentence: "We will [do X]." Followed by the rationale paragraph from Step 4.]

## What Was Not Chosen

[For each rejected route: one sentence on why it was eliminated.]

## Consequences

[What becomes easier? What becomes harder? What new decisions does this force? What technical debt does this accept?]

## Propagation

[The checklist from Step 5.]
```

### Step 7: NUMBER

Before saving, check the existing ADR numbers in the `decisions/` directory.

1. Run `glob` on `decisions/` to list existing ADR files.
2. Find the highest existing number.
3. Assign the next sequential number (e.g., if `decisions/020-*.md` exists, this ADR is `021`).
4. Use three-digit zero-padded numbers: `001`, `012`, `021` — never `1`, `12`, `21`.
5. Save the file as `decisions/NNN-[kebab-case-title].md`.

If no `decisions/` directory exists, create it and start at `001`.

## IV. Quality Checklist

- [ ] Decision topic is clearly stated (not just a solution description)
- [ ] At least 3 routes considered (if genuinely distinct routes exist)
- [ ] Comparison table fills all four columns for each route
- [ ] Decision sentence is unambiguous — "we will X", not "we should probably X"
- [ ] Rejected routes explained (not just listed)
- [ ] Consequences section covers both positive and negative
- [ ] Propagation checklist is specific — named files, not vague categories
- [ ] ADR number is sequential and zero-padded
- [ ] File saved to `decisions/NNN-title.md`

## V. Common Pitfalls

- **Writing the conclusion before the routes.** If you know the answer before writing the ADR, you will unconsciously bias the route descriptions to justify your conclusion. Write the routes honestly, then decide.
- **Vague consequences.** "This will make the system more maintainable" is not a consequence. "Adding a new route handler now requires updating two files instead of one" is a consequence.
- **Missing the propagation checklist.** The ADR is not done when the markdown is written. The ADR is done when the decision is implemented and the consequences are propagated.
- **ADR inflation.** Not every decision needs an ADR. Save the format for decisions that are hard to reverse or will confuse future contributors.
- **Superseding without linking.** If a new ADR supersedes an old one, update the old ADR's Status field to "Superseded by ADR-NNN" and add a link. The old ADR should remain — it shows the reasoning that led to the change.

## VI. Output

- ADR markdown file saved to `decisions/NNN-[kebab-case-title].md`
- Propagation checklist printed to conversation for immediate action tracking
- If decisions/ directory was created: note that to the user

## Examples

**Scenario 1:** "We need to record why we chose Gateway port 7340 instead of 8080."
→ ADR documents the context (port conflict with common dev server defaults), routes (8080, 3000, 7340, custom env var), decision (7340 as default with env override), consequences (all CLI config must be updated, README must be updated), propagation checklist with 4 items.

**Scenario 2:** "ADR for switching from per-session SQLite to a shared D1 database."
→ ADR documents forces (multi-process access, VPS portability), routes (SQLite WAL, Postgres, D1, Redis), comparison table with risk/time/tradeoff, decision (D1 for Cloudflare-native simplicity), what was not chosen (Postgres — operational burden; Redis — not a primary store), consequences (session continuity across restarts, new D1 migration tooling required), propagation (5 files in Gateway server/database/).

## Edge Cases

- If the decision is already made and the ADR is being written retroactively, set Status to "Accepted" rather than "Proposed". Note the actual decision date if known.
- If the decision is genuinely between only two routes, that is acceptable — do not invent a third route to fill the template. Document why only two routes were viable.
- If external constraints eliminate all but one route, document that explicitly in the Context section. An ADR that records "we had no choice because X" is still valuable — it prevents the question from being re-raised.

## Anti-Patterns

- Writing ADRs after decisions are irreversible with no propagation checklist — the checklist is the mechanism that makes ADRs affect actual code.
- Treating the ADR format as bureaucracy to get through quickly — the comparison table is the most valuable part. A rushed table produces a useless ADR.
- Storing ADRs in a wiki instead of the repo — ADRs that live outside version control become stale silently. The repo is the source of truth.
