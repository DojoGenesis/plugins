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
version: "1.0.0"
model: sonnet
---

# Seed Curator

Manages the full seed lifecycle — from planting raw patterns through harvesting session insights to elevating proven seeds into reusable skills.

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
