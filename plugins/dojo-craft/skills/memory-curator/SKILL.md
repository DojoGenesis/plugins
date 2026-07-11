---
name: memory-curator
description: "Two-tier memory management: write, update, prune, and search memories with semantic deduplication. Maintains MEMORY.md index under 200 lines."
triggers:
  - "manage memories"
  - "curate memory"
  - "prune memories"
  - "memory health"
  - "organize memories"
version: "1.0.1"
model: sonnet
category: remember-continue
---

# Memory Curator

Manages the persistent memory system — writes, updates, prunes, and deduplicates memories while keeping the MEMORY.md index lean and navigable.

## Philosophy

Memory degrades in two directions: it grows bloated with stale or duplicate entries until the index is unnavigable, or it gets pruned too aggressively and the agent forgets corrections that cost real sessions to learn. This skill walks the middle path — surgically removing what's derivable from code or superseded by later facts, while protecting user preferences, feedback corrections, and hard-won patterns. A healthy memory store is a compressed model of the project, not a transcript of every session.

## When to Use

- MEMORY.md index is approaching or exceeding 200 lines
- Convergence check flags GROWING or CRITICAL memory health
- After a major project milestone where many "in progress" entries are now done
- Session-end ritual when the session harvested new memories and the index needs updating
- Before a long absence where stale memories could mislead the next session
- Any time the agent or user notices duplicate facts or contradictory memories

Do NOT run aggressively after a single session without a convergence signal — premature pruning removes memories before they've proven their value.

## Workflow

### 1. SCAN
Read MEMORY.md index and all referenced memory files in the memory directory. Build an inventory of:
- Total memory count
- Categories represented
- Line count of MEMORY.md (warn if approaching 200-line limit)
- Any orphaned files (not referenced in index) or broken links (referenced but missing)

### 2. DEDUP
Detect semantically duplicate memories — same fact stored with different wording. Criteria:
- Same file paths or function names referenced
- Same decision recorded with different timestamps
- Same feedback captured in multiple sessions
Flag duplicates for merge, never auto-delete.

### 3. STALE
Identify memories referencing things that no longer exist:
- File paths that return 404
- Function/variable names not found in codebase
- Project states that have been superseded (e.g., "in progress" when actually shipped)
- Version numbers that are outdated

### 4. MERGE
Combine related memories that cover the same topic:
- Two user-profile memories → single comprehensive profile
- Multiple feedback entries about the same convention → one authoritative entry
- Project memories tracking the same initiative at different points → latest state only
Preserve the most specific, actionable content from each source.

### 5. PRUNE
Remove memories that are:
- **Derivable** from current code (architecture that's obvious from reading the source)
- **Stale beyond repair** (references entirely removed codebases or abandoned projects)
- **Duplicated** after merge step
Never prune: user preferences, feedback corrections, reference pointers to external systems.

### 6. INDEX
Rebuild MEMORY.md:
- One line per entry, under 150 characters
- Grouped by semantic category (User, Feedback, Project, Reference, Seeds, etc.)
- Most-referenced memories near the top of each group
- Total line count must stay under 200

### 7. REPORT
Output summary:
- Memories scanned: N
- Duplicates merged: N
- Stale entries removed: N
- Index lines: N/200
- Health status: HEALTHY (<150 lines) / GROWING (150-180) / CRITICAL (>180)

## Anti-patterns
- Never aggressively prune — when in doubt, keep the memory
- Never rewrite memory content for style — preserve the user's original voice
- Never merge memories across fundamentally different domains
- Never delete feedback memories without explicit user confirmation

## Example

Index is at 187 lines (GROWING). Running the curator:
- SCAN finds 3 orphaned files (referenced in index but missing from disk) and 2 broken links
- DEDUP identifies a project state entry from 3 months ago and a newer entry covering the same project — the older one says "in progress," the newer says "shipped"
- STALE finds a memory pointing to `src/legacy/payments.js` which no longer exists in the repo
- MERGE collapses the two project state entries into the newer one, preserving the shipped date
- PRUNE removes the broken file reference and the superseded project state
- INDEX is rebuilt at 171 lines — GROWING, but improved
- REPORT: 2 merged, 3 removed, index 171/200 (GROWING)

## Quality Checklist

- [ ] SCAN step ran before any mutation — total count and line count confirmed
- [ ] No memory was deleted without first appearing in DEDUP or STALE output
- [ ] Feedback memories and user preference memories were NOT pruned without explicit user confirmation
- [ ] Original wording of kept memories is preserved verbatim (no style rewrites)
- [ ] Merged memories preserve the most specific content from each source
- [ ] Final MEMORY.md index line count is reported
- [ ] Health status label (HEALTHY / GROWING / CRITICAL) is explicit in output

## Related Skills

- `convergence-checker` — triggers memory-curator runs based on session count and index size thresholds
- `seed-curator` — manages the seed library, which lives alongside the memory system; coordinate when the boundary between seeds and memories is blurry
