---
name: retro
description: Runs a sprint retrospective. Use when a sprint ends.
argument_hint: "<sprint name, version, or time period>"
skill: skills/retrospective/SKILL.md
---

# /retro

Run a structured sprint retrospective to harvest learnings from a completed sprint, release, or time period.

## Behavior

### 1. Initiate

Ask the user what period or milestone to reflect on. Accept: sprint number, version, date range, or informal period ("the last two weeks").

### 2. Gather Context

If connected tools are available, pull relevant data:

- **~~project tracker** — Pull completed tickets, velocity, and burndown data
- **~~chat** — Scan for notable discussions, decisions, and blockers
- **~~repository** — Pull merged PRs, deployment history, and code changes

If no integrations are connected, ask the user to share context conversationally.

### 3. Facilitate the Three Core Questions

Ask these **one at a time, conversationally**. Wait for a response before asking the next. Never dump all three at once.

**Question 1: What went well?**
Celebrate successes. Name specific wins. Acknowledge contributors. What should we amplify?

**Question 2: What was hard?**
Identify pain points without blame. Focus on systemic issues, not individual failures. What were the sources of friction or difficulty?

**Question 3: What would we do differently?**
Concrete changes, not vague intentions. Each "differently" should be actionable. What specific changes can we make?

### 4. Synthesize Learnings

After all three questions are answered, produce:

**Key Themes & Insights:**

| Theme | Insight | Evidence | Recommended Action |
| :--- | :--- | :--- | :--- |
| [Theme] | [What we learned] | [Specific examples] | [Concrete next step] |

**Seeds for Memory Garden:**
For patterns worth preserving, distill into seeds. Offer to `/plant` each via the wisdom-garden plugin.

- **Seed:** [Name] — *Why it matters:* [Explanation] — *Revisit trigger:* [When to remember this]

**Closing Statement:**
End with a gratitude-based closing that acknowledges the work done and sets intention for the next cycle. This is a celebration of learning, not a judgment.

### 5. Save

Save the retrospective as `docs/retrospectives/[YYYY-MM-DD]_retro_[sprint].md`.
