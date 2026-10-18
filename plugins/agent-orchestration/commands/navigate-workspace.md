---
description: Navigate and organize a shared agent workspace.
---

# `/navigate-workspace` — Navigate and Organize a Shared Agent Workspace

Navigate, organize, and maintain shared agent workspaces. **A workspace is a thinking room, not a file dump** — structure enables clarity, clarity enables collaboration.

## Philosophy

A shared workspace is where agents collaborate, think together, and build shared context. Without structure, it becomes chaotic. With structure, it becomes a powerful tool for coordination and knowledge building.

**Core Principles:**
- Navigate by purpose, not by time
- Read surgically, not exhaustively
- Link to content, don't duplicate it
- Maintain actively, not passively

## When to Use

Use `/navigate-workspace` when:
- Starting work in a shared repository
- Looking for existing handoffs, decisions, or specifications
- Organizing completed work
- Identifying stale or orphaned content
- Coordinating with other agents across sessions
- Building situational awareness of workspace state

## Workflow

### Step 1: Scan the Workspace

If no specific path is provided, scan the default workspace structure:

```bash
workspace/
├── README.md                    # Workspace overview
├── 00_Active/                   # Current work in progress
│   ├── discussions/             # Active discussions
│   ├── drafts/                  # Work in progress
│   ├── decisions/               # Decisions made
│   └── handoffs/                # Pending handoffs
├── 01_Specifications/           # Finalized specs
├── 02_Research/                 # Research findings
├── 03_Memory/                   # Shared knowledge base
│   ├── seeds/                   # Reusable patterns
│   └── learnings/               # Lessons learned
├── 04_Artifacts/                # Generated outputs
└── 05_Archive/                  # Completed work
```

Use these commands to scan:
```bash
# List directory structure
find workspace/ -type d -maxdepth 2 | sort

# Count items by category
echo "Active discussions: $(find workspace/00_Active/discussions/ -name '*.md' | wc -l)"
echo "Pending handoffs: $(find workspace/00_Active/handoffs/ -name '*.md' | wc -l)"
echo "Finalized specs: $(find workspace/01_Specifications/ -name '*.md' | wc -l)"

# Find recent activity (last 7 days)
find workspace/ -name '*.md' -mtime -7 | sort

# Find stale items (untouched for >14 days)
find workspace/00_Active/ -name '*.md' -mtime +14
```

### Step 2: Present Workspace Map

Create a clear visual map showing:

**Active Work** (what's in progress):
- Discussions being developed
- Drafts under review
- Decisions pending finalization

**Pending Handoffs** (what's waiting for attention):
- Handoffs waiting to be accepted
- Blocked handoffs (dependencies not met)

**Recent Decisions** (last 7 days):
- Decisions made with attribution
- Impact areas affected

**Stale Items** (untouched for >14 days):
- Orphaned discussions
- Abandoned drafts
- Old handoffs never completed

**Example Output:**

```markdown
# Workspace Map: agent-collab-repo

**Last Updated:** 2026-02-11

## Active Work (7 items)

### Discussions (3)
- `2026-02-10_context_compression_manus.md` (Active)
- `2026-02-09_memory_architecture_cipher.md` (Active)
- `2026-02-08_seed_extraction_manus-cipher.md` (Active)

### Drafts (2)
- `2026-02-11_breadcrumb_spec_manus.md` (Draft)
- `2026-02-10_parallel_tracks_spec_cipher.md` (Draft)

### Decisions (2)
- `2026-02-11_auth_bypass_cruz.md` (Final)
- `2026-02-10_entity_backend_priority_cruz.md` (Final)

## Pending Handoffs (2)

- `2026-02-11_handoff_breadcrumb_implementation.md` → Zenflow (Ready)
- `2026-02-09_handoff_research_compression.md` → Cipher (Blocked: Awaiting decision on memory arch)

## Recent Decisions (Last 7 Days)

1. **Auth Bypass** (Cruz, 2026-02-11)
   - Skip production auth in v0.2.0
   - Impact: Unblocks frontend work, defers auth to v0.2.2

2. **Entity Backend Priority** (Cruz, 2026-02-10)
   - Build entity backend first
   - Impact: Reshuffles parallel track allocation

## Stale Items (>14 Days)

⚠️ **3 items need attention:**
- `2026-01-25_oauth_discussion_manus.md` (17 days old, never finalized)
- `2026-01-28_api_design_draft_cipher.md` (14 days old, no updates)
- `2026-01-20_handoff_frontend_refactor.md` (22 days old, never accepted)

**Recommended Actions:**
- Archive or finalize OAuth discussion
- Check in on API design draft status
- Investigate why frontend refactor handoff wasn't accepted
```

### Step 3: Offer Actions

Based on the workspace state, offer context-aware actions:

**If there are pending handoffs:**
- "Read handoff: [filename]"
- "Accept handoff: [filename]"
- "Reject handoff: [filename] (with reason)"

**If there are stale items:**
- "Archive stale items"
- "Review and finalize: [filename]"
- "Delete abandoned work: [filename]"

**If workspace is healthy:**
- "Start a new discussion"
- "Create a handoff package"
- "Document a decision"
- "Update workspace README"

### Step 4: Execute Selected Action

Based on user selection:

**"Read a handoff":**
- Read the full handoff package
- Present summary with key sections
- Ask if they want to accept or need more information

**"Accept a handoff":**
- Confirm acceptance with user
- Move handoff to agent's active work folder
- Update workspace index
- Begin work on the task

**"Archive completed work":**
- Identify items marked as "Completed" or "Final"
- Move to `05_Archive/by-date/YYYY-MM/` or `05_Archive/by-topic/[topic]/`
- Update workspace README to remove from active lists
- Preserve links for future reference

**"Start a discussion":**
- Create new discussion file in `00_Active/discussions/`
- Use discussion template (see workspace-navigation skill)
- Set up frontmatter with metadata
- Update workspace README

## Integration with Connectors

### With ~~repository (GitHub)
- Show open PRs related to active work
- Link handoffs to specific branches
- Track commit activity on specs

### With ~~project tracker (Linear, Asana)
- Cross-reference workspace items with tracker tickets
- Show dependencies between workspace and external tasks
- Sync status updates bidirectionally

### With ~~knowledge base (Notion)
- Pull relevant documentation into workspace context
- Link workspace decisions to knowledge base records
- Sync finalized specs to centralized knowledge base

### With ~~chat (Slack)
- Notify teams about new handoffs or decisions
- Post workspace map to status channel
- Enable workspace discussions in chat threads

## Advanced Navigation

### Search by Topic

```bash
# Find all content about "memory architecture"
grep -r "memory architecture" workspace/ --include="*.md"

# Find content tagged with specific tags
grep -r "tags: .*memory" workspace/ --include="*.md"
```

### Search by Author

```bash
# Find all content by Manus
grep -r "author: Manus" workspace/ --include="*.md"

# Find collaborative work (multiple authors)
grep -r "participants:" workspace/ --include="*.md"
```

### Search by Status

```bash
# Find all active discussions
grep -r "status: Active" workspace/00_Active/discussions/ --include="*.md"

# Find all finalized decisions
grep -r "status: Final" workspace/00_Active/decisions/ --include="*.md"
```

### Track Dependencies

```bash
# Find content referencing a specific spec
grep -r "breadcrumb_navigation.md" workspace/ --include="*.md"

# Find handoffs waiting on decisions
grep -r "Blocked:" workspace/00_Active/handoffs/ --include="*.md"
```

## Maintenance Actions

### Weekly Review (Automated)

When user runs `/navigate-workspace` with no arguments, perform weekly review:

1. **Review Active Directory:**
   - List all items in `00_Active/`
   - Identify items with `status: Final` → Move to appropriate section
   - Identify items with `status: Completed` → Archive
   - Find items older than 14 days → Flag as stale

2. **Update Workspace README:**
   - Refresh active work lists
   - Update decision log
   - Reflect current priorities
   - Update navigation guide if structure changed

3. **Compress Old Discussions:**
   - For discussions >30 days old in Archive
   - Extract key insights into memory
   - Create summary file
   - Delete verbose original (keep summary)

### Monthly Audit

For monthly reviews, add:

1. **Review Specifications:**
   - Check for outdated specs (modified >3 months ago)
   - Verify links are still valid
   - Update if needed or mark as deprecated

2. **Review Memory:**
   - Check for unused seeds (never referenced)
   - Consolidate duplicate learnings
   - Archive obsolete patterns

3. **Refactor Structure:**
   - Reorganize if directories are overgrown
   - Split large sections into subsections
   - Update README to reflect new structure

## Workspace Quality Checklist

Before finishing navigation, verify:

- [ ] All active items have clear status (Draft/Active/Final)
- [ ] No orphaned files (every file linked from somewhere)
- [ ] Stale items are addressed (archived or finalized)
- [ ] README reflects current workspace state
- [ ] Pending handoffs have clear next steps
- [ ] Recent decisions are documented with rationale

## Examples

### Example 1: Starting Work in New Workspace

**User:** `/navigate-workspace`

**Response:**
```
Welcome to the agent-collab-repo workspace!

I've scanned the workspace and here's what I found:

**Active Work:** 7 items (3 discussions, 2 drafts, 2 decisions)
**Pending Handoffs:** 2 (1 ready, 1 blocked)
**Recent Activity:** 5 items updated in last 7 days
**Stale Items:** 3 items >14 days old

What would you like to do?
1. Read pending handoffs
2. Review recent decisions
3. Check stale items
4. Start new work
5. Archive completed items
```

### Example 2: Finding Specific Content

**User:** `/navigate-workspace find discussions about memory`

**Response:**
```
Found 3 discussions about memory:

1. **Memory Architecture** (Cipher, 2026-02-09)
   - Status: Active
   - Path: `00_Active/discussions/2026-02-09_memory_architecture_cipher.md`
   - Summary: Exploring three-tier memory system (working/episodic/semantic)

2. **Memory Garden Design** (Manus, 2026-02-02)
   - Status: Archived
   - Path: `05_Archive/by-topic/memory/2026-02-02_memory_garden_design_manus.md`
   - Summary: Original design for semantic memory storage

3. **Context vs. Memory** (Manus-Cipher, 2026-02-01)
   - Status: Final → Moved to Specifications
   - Path: `01_Specifications/architecture/context_vs_memory.md`
   - Summary: Clarifies distinction between transient context and persistent memory

Would you like to read any of these?
```

## Best Practices

1. **Read README First**
   - Always start with workspace README.md
   - Understand conventions before navigating

2. **Navigate by Purpose**
   - Don't browse chronologically
   - Identify your goal, then navigate to relevant section

3. **Use Grep for Speed**
   - Search by topic, author, or status
   - Much faster than manual browsing

4. **Keep Workspace Clean**
   - Archive completed work weekly
   - Delete abandoned drafts monthly
   - Link related content together

5. **Update the Index**
   - After significant changes, update README
   - Keep navigation current for other agents

## Related Skills

- `workspace-navigation` — Full skill documentation
- `handoff-protocol` — For accepting and processing handoffs
- `decision-propagation` — For documenting and propagating decisions
