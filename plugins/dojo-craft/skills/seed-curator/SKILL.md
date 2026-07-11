---
name: seed-curator
description: "Seed lifecycle management: plant new seeds from experiences, harvest insights from sessions, search the seed library, and elevate proven seeds to skills."
triggers:
  - "manage seeds"
  - "curate seeds"
  - "harvest seed"
  - "plant seed"
  - "seed health"
  - "elevate seed"
version: "1.0.1"
model: sonnet
category: seed-lifecycle
---

# Seed Curator

Manages the full seed lifecycle — from planting raw patterns through harvesting session insights to elevating proven seeds into reusable skills.

## Philosophy

Skills are the endpoint; seeds are the evidence path. A good skill is never invented — it's distilled from repeated real experience that earned a pattern status through validated use. Seeds are the intermediate form: a named insight with a confidence score and counter-examples, held in the library until the pattern is proven enough to justify a full SKILL.md with triggers and workflow. Without seed management, patterns get lost between sessions or promoted too early (becoming brittle skills) or too late (staying buried in transcripts forever).

## When to Use

- **plant** — You just encountered an approach that worked in a non-obvious way and want to capture it before the session ends
- **harvest** — At session close, scan for corrections, wins, or friction that should be captured as candidate seeds
- **search** — Before starting a task, check whether the seed library has relevant patterns (especially for debugging or architectural decisions)
- **elevate** — A seed has accumulated high confidence across multiple real uses and is ready to become a SKILL.md
- **audit** — Periodic check of the seed library for stale references or low-quality entries

Do NOT use `elevate` immediately after planting a seed — seeds need confidence ≥ 0.8 and 3+ independent applications before elevation.

## Workflow

### 1. MODE
Determine the operation from user intent:
- **plant** — Extract a new seed from a specific experience or insight
- **harvest** — Scan a recent session for candidate seeds
- **search** — Find seeds relevant to a current situation
- **elevate** — Promote a proven seed to a full SKILL.md
- **audit** — Check seed library health

### 2. PLANT (when mode = plant)
Extract a reusable pattern:
- **Name**: Short, memorable, hyphenated (e.g., `compilation-as-contract`)
- **Source**: Where this pattern was observed (session, project, incident)
- **Confidence**: 0.0-1.0 based on how many times it's been validated
- **Tags**: 3-5 categorization tags
- **Pattern**: What the seed captures — the reusable insight
- **When to use**: Situations where this seed applies
- **Example**: Concrete instance of the pattern in action
- **Counter-example**: When this pattern does NOT apply
Write as YAML-fronted markdown file.

### 3. HARVEST (when mode = harvest)
Scan the current or recent session for seed candidates:
- Corrections received from the user (feedback → pattern)
- Approaches that worked unexpectedly well (success → pattern)
- Non-obvious decisions that required investigation (discovery → pattern)
- Friction points that were resolved (obstacle → pattern)
Present candidates to user for confirmation before writing files.

### 4. SEARCH (when mode = search)
Given a situation description, score all seeds by relevance:
- Tag match (exact tag = 3 points, partial = 1)
- Description keyword overlap (each matching word = 1 point)
- Confidence weighting (score × confidence)
Return ranked list with seed name, confidence, and one-line relevance explanation.

### 5. ELEVATE (when mode = elevate)
For seeds meeting promotion criteria:
- Confidence ≥ 0.8
- Applied 3+ times across different contexts
- No contradicting seeds in the library
Generate a SKILL.md draft following the skill-creation skill's format:
- YAML frontmatter with name, description, triggers, version
- Structured workflow steps derived from the seed's pattern
- Anti-patterns derived from the seed's counter-examples

### 6. AUDIT (when mode = audit)
Check all seeds for:
- Stale references (files/functions that no longer exist)
- Low confidence + no recent use (candidates for archival)
- Contradictions between seeds (same situation, opposite advice)
- Missing fields (no counter-example, no tags, no confidence score)
Produce audit report with recommendations.

### 7. OUTPUT
Produce the appropriate artifact based on mode:
- plant → seed file written to memory directory
- harvest → candidate list with user confirmation prompts
- search → ranked seed list
- elevate → SKILL.md draft for review
- audit → health report with action items

## Best Practices

- **Confirm before writing.** In harvest mode, always present candidates to the user before writing any file — they know which patterns are worth keeping.
- **Counter-examples are mandatory for plant.** A seed without a counter-example is a rule, not a pattern. Every seed should state when it does NOT apply.
- **Keep confidence honest.** First observation = 0.3–0.4. Second independent validation = 0.6–0.7. Three or more contexts = 0.8+. Never start a seed at 0.8.
- **Seeds are not memories.** Memories capture facts about projects and preferences. Seeds capture reusable behavioral patterns. Overlap is a signal to choose — don't maintain the same insight in both stores.
- **Elevation is a draft, not a deploy.** The SKILL.md produced by `elevate` is a draft for review. The user decides when it goes into the skills directory.

## Example

Session ends. User asks to harvest seeds.

The curator scans the session and identifies three candidates:
1. A correction: "always check config before debugging code" — seen twice now, confidence 0.6, tagged `debugging, config`
2. An approach that worked: using Grep before Read for large files — already exists as a seed at confidence 0.7 (update confidence, don't duplicate)
3. A friction point resolved: PowerShell commit messages need heredoc to avoid variable interpolation — new seed, confidence 0.4

Candidates presented to user. User confirms #1 and #3, declines #2 (already covered). Two seed files written; #2 gets a confidence bump in its existing file.

Later, #1 accumulates two more confirmations across different sessions (confidence now 0.85, 3+ uses). User runs `elevate`. A SKILL.md draft is produced with triggers, workflow steps, and anti-patterns derived from the seed's counter-example. Draft lands in a review location — not deployed automatically.

## Quality Checklist

- [ ] Mode determined before any file reads or writes
- [ ] In harvest mode: candidates presented before any file is written
- [ ] Every new seed includes: name, source, confidence, tags, pattern, when-to-use, example, counter-example
- [ ] Confidence value is within the honest range for number of observations (new seed ≤ 0.5)
- [ ] No seed was elevated with confidence < 0.8 or fewer than 3 documented uses
- [ ] Elevated SKILL.md is labeled as a draft and placed for review, not written directly into the skills directory
- [ ] Audit report distinguishes stale/contradicting/missing-fields as separate categories
- [ ] No duplicate seeds created — search the library before planting

## Related Skills

- `memory-curator` — manages the parallel memory store; coordinate when an insight could live in either system
- `convergence-checker` — seed audit can be triggered as part of a convergence run
