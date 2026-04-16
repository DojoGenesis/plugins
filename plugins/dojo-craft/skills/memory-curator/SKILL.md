---
name: memory-curator
description: "Two-tier memory management: write, update, prune, and search memories with semantic deduplication. Maintains MEMORY.md index under 200 lines."
triggers:
  - "manage memories"
  - "curate memory"
  - "prune memories"
  - "memory health"
  - "organize memories"
version: "1.0.0"
model: sonnet
---

# Memory Curator

Manages the persistent memory system — writes, updates, prunes, and deduplicates memories while keeping the MEMORY.md index lean and navigable.

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
