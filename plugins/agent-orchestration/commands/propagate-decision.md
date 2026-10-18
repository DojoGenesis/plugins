---
description: Propagate a decision across affected documents.
---

# `/propagate-decision` — Propagate a Decision Across the Ecosystem

Record a decision and systematically propagate its effects across all affected documents and systems. **Decisions propagate or they die** — a decision made in one place that doesn't reach other agents might as well not have been made.

## Philosophy

Architectural and strategic decisions create ripples across an entire ecosystem of interdependent files, systems, and teams. Without a propagation protocol, decisions become stranded. Different documents contradict each other. The system becomes incoherent.

**Core Principles:**
- Record decisions at source with full reasoning
- Trace dependencies before editing
- Update surgically, not wholesale
- Decisions are infrastructure, not courtesy
- Propagation is mandatory, not optional

## When to Use

Use `/propagate-decision` when:
- A human provides answers to open questions in a scout or spec
- An architectural decision changes the scope of a release or work track
- A decision in one document affects content, sequencing, or priorities of others
- You need to defer work from one release to a later one
- The STATUS file or master tracking document is out of sync with decisions
- Any time a decision made in one place must be reflected in many places

## Workflow

### Step 1: Articulate the Decision

Ask the user to provide:

**Decision:** What was decided (one clear sentence)

**Rationale:** Why this choice was made

**Alternatives Considered:** What was NOT chosen and why

**Impact Scope:** What parts of the system/process are affected

**Effective Date:** When does this take effect

**Example:**
```
Decision: Skip production auth layer in v0.2.0; ship with debug token instead

Rationale: Unblocks frontend integration work immediately; auth hardening can move to v0.2.2 without blocking current sprint

Alternatives Considered:
- Build basic auth (rejected: adds 2-3 weeks to timeline)
- Use third-party auth (rejected: external dependency, integration complexity)

Impact Scope:
- v0.2.0 scope (removes auth requirement)
- v0.2.2 scope (adds auth implementation)
- Frontend work (can proceed immediately)
- Security posture (temporary degradation, acceptable for internal alpha)

Effective Date: Immediately (2026-02-11)
```

### Step 2: Record Decision at Source

Locate the document where the decision was made (scout, spec, or master plan).

Replace any "Open Questions" section with "Decisions ([Name], [Date])". Number each decision:

```markdown
## Decisions (Cruz, 2026-02-11)

### 1. Auth Bypass

**Decision:** Skip production auth layer in v0.2.0; ship with debug token instead.

**Rationale:** Unblocks frontend integration work immediately; auth hardening can move to v0.2.2 without blocking current sprint.

**Alternatives Considered:**
- Build basic auth → Rejected: adds 2-3 weeks to timeline
- Use third-party auth → Rejected: external dependency, integration complexity

**Impact Scope:**
- v0.2.0 scope (removes auth requirement)
- v0.2.2 scope (adds auth implementation)
- Frontend work (can proceed immediately)
- Security posture (temporary degradation, acceptable for internal alpha)

**Effective Date:** 2026-02-11

---

### 2. Entity Backend Priority

**Decision:** Build entity-centric backend first, before other subsystems.

**Rationale:** Reduces scope of v0.2.1 and focuses team on core abstraction.

**Alternatives Considered:**
- Parallel development of all subsystems → Rejected: coordination overhead
- Start with API gateway → Rejected: needs entities first

**Impact Scope:**
- Defers non-entity tasks to v0.2.1
- Reshuffles parallel track allocation
- Affects frontend integration timeline

**Effective Date:** 2026-02-11
```

**Format Requirements:**
- Capture exact words (don't paraphrase)
- Include attribution (who decided) and date
- Number decisions for reference
- Document alternatives considered (not just chosen option)

### Step 3: Trace Document Dependencies

Before editing anything, identify ALL affected documents:

**Common Dependency Patterns:**

**Master Plan / Roadmap:**
- Scope blocks (what's in/out of each release)
- Dependency graph (edges between tasks)
- Constraints (limitations acknowledged)
- Parallel track allocation (how work is distributed)
- Next steps (sequencing affected)

**Other Scouts / Specs:**
- Promoted (dependencies now met, can proceed)
- Deferred (dependencies removed or pushed later)
- Content updates (references to the decision area)

**Implementation Prompts:**
- May need regeneration if scope changed
- Updated task lists
- Modified success criteria

**STATUS.md / Tracking Files:**
- Always needs updating
- Decision log
- Scope summaries
- Architecture summaries
- Next steps

**Walk through each document systematically:**
```bash
# Find all documents that might reference the decision
grep -r "auth" docs/ --include="*.md" | grep -v ".git"

# Find all documents referencing the affected scope (v0.2.0)
grep -r "v0.2.0" docs/ --include="*.md"

# Find STATUS and tracking files
find docs/ -name "STATUS.md" -o -name "*_tracking.md"
```

**Create a propagation checklist:**
- [ ] Master plan: `docs/v0.2.0/master_plan.md`
- [ ] Related scout: `docs/v0.2.0/scouts/frontend_integration.md`
- [ ] Implementation prompt: `docs/v0.2.0/prompts/backend_implementation.md`
- [ ] STATUS file: `docs/v0.2.0/STATUS.md`
- [ ] v0.2.2 scope: `docs/v0.2.2/master_plan.md`

### Step 4: Propagate to Each Dependent Document

For each dependent document, make **surgical edits** — change only the affected sections.

**In Master Plans:**
```markdown
## Scope

### In Scope (v0.2.0)
- Entity-centric backend ← UPDATED: promoted to priority
- Frontend breadcrumb navigation
- ~~Production auth layer~~ ← REMOVED: deferred to v0.2.2

### Out of Scope (Deferred)
- Production auth layer → v0.2.2 ← ADDED: decision on 2026-02-11
- OAuth integration → v0.2.2
```

**In Related Scouts:**
```markdown
## Deferral Notice

This work has been deferred to v0.2.2 based on decision made 2026-02-11.

**Decision Reference:** Auth Bypass (Cruz, 2026-02-11)

**Reasoning:** Frontend integration work can proceed with debug token; full auth implementation moves to v0.2.2 without blocking current sprint.

**Proposed Timeline:** v0.2.2 (target: March 2026)

**Dependencies for Reactivation:**
- v0.2.0 completion
- v0.2.1 scope finalized
- Auth requirements review completed
```

**In STATUS.md:**
```markdown
## Key Architecture Decisions

### Auth Bypass (Cruz, 2026-02-11)
**Decision:** Skip production auth in v0.2.0; ship with debug token
**Impact:** Unblocks frontend work immediately; auth moves to v0.2.2
**Status:** Active

### Entity Backend Priority (Cruz, 2026-02-11)
**Decision:** Build entity-centric backend first
**Impact:** Reshuffles v0.2.0/v0.2.1 scope allocation
**Status:** Active
```

### Step 5: Update Master Tracking

STATUS.md is the coherence checkpoint. Update it last to ensure it reflects all changes:

1. **Add Decisions Block** (if not present)
2. **Update Scope Tables** (what's in/out of each release)
3. **Update Dependency Graph** (if shown visually)
4. **Update Next Steps** (reorder if sequencing changed)
5. **Refresh Architecture Summary** (if affected)

**Example STATUS.md Update:**
```markdown
# Project Status — v0.2.0

**Last Updated:** 2026-02-11 | **Status:** In Progress

## Key Architecture Decisions

### Auth Bypass (Cruz, 2026-02-11)
**Decision:** Skip production auth in v0.2.0; ship with debug token instead
**Rationale:** Unblocks frontend integration immediately
**Impact:**
- v0.2.0 scope reduced (removes auth)
- v0.2.2 scope increased (adds auth)
- Frontend can proceed without waiting

### Entity Backend Priority (Cruz, 2026-02-11)
**Decision:** Build entity-centric backend first, before other subsystems
**Rationale:** Focuses effort on core abstraction
**Impact:**
- Defers non-entity work to v0.2.1
- Reshuffles parallel track allocation

## Scope by Release

| Release | In Scope | Deferred | Complete |
|---------|----------|----------|----------|
| v0.2.0 | Entity backend, Breadcrumb nav | ~~Auth layer~~ → v0.2.2 | 40% |
| v0.2.1 | API gateway, Non-entity tasks | TBD | 0% |
| v0.2.2 | **Auth layer** (deferred from v0.2.0), OAuth | TBD | 0% |

## Next Steps

1. ✅ Complete entity backend implementation
2. ✅ Integrate breadcrumb navigation
3. ⏳ Frontend integration (unblocked by auth bypass decision)
4. ⏳ v0.2.0 QA and testing
5. 📅 Begin v0.2.1 planning
```

### Step 6: Verify Coherence

After propagation, verify no contradictions remain:

**Coherence Checklist:**
- [ ] Decision recorded at source with full context
- [ ] All dependent documents identified and updated
- [ ] No documents still reference old scope or pre-decision state
- [ ] Cross-references consistent (if doc A says "deferred to v0.2.2," doc B acknowledges it)
- [ ] STATUS.md reflects all changes
- [ ] Document copies synced if they exist in multiple locations

**Verification Commands:**
```bash
# Check for orphaned references to old scope
grep -r "production auth" docs/v0.2.0/ --include="*.md"

# Verify cross-references
grep -r "v0.2.2" docs/ --include="*.md" | grep -i "auth"

# Check STATUS.md is current
git diff docs/v0.2.0/STATUS.md
```

## Integration with Connectors

### With ~~repository (GitHub)
- Commit decision as atomic change
- Link decision to related PRs or issues
- Use conventional commit message: `docs(decision): Record auth bypass for v0.2.0`

### With ~~project tracker (Linear, Asana)
- Create tickets for each touchpoint affected
- Update ticket dependencies
- Link tickets to decision document

### With ~~chat (Slack)
- Announce decision in relevant channel
- Share decision document link
- Enable team discussion

### With ~~knowledge base (Notion)
- Sync decision to centralized decision log
- Link to affected documentation
- Update architecture diagrams if needed

## Examples

### Example 1: Scope Decision Propagation

**User:** `/propagate-decision — Auth bypass for v0.2.0`

**Decision Articulation:**
```
Decision: Skip production auth layer in v0.2.0; ship with debug token

Rationale: Unblocks frontend immediately; auth can move to v0.2.2

Alternatives:
- Build basic auth (rejected: 2-3 week delay)
- Use third-party auth (rejected: complexity)

Impact Scope:
- v0.2.0 scope (removes auth)
- v0.2.2 scope (adds auth)
- Frontend work (unblocked)
- Security (temporary degradation, acceptable for alpha)

Effective Date: 2026-02-11
```

**Trace Dependencies:**
```
Affected Documents:
✓ docs/v0.2.0/master_plan.md (scope table)
✓ docs/v0.2.0/scouts/frontend_integration.md (can now proceed)
✓ docs/v0.2.0/scouts/auth_implementation.md (deferred)
✓ docs/v0.2.2/master_plan.md (scope increased)
✓ docs/v0.2.0/STATUS.md (decisions, scope, next steps)
✓ docs/v0.2.0/prompts/backend_implementation.md (updated requirements)
```

**Propagation:**
1. Record decision in `scouts/auth_implementation.md`
2. Update `master_plan.md` scope table (remove auth from v0.2.0)
3. Update `frontend_integration.md` scout (now unblocked)
4. Add deferral note to `auth_implementation.md` scout
5. Update `v0.2.2/master_plan.md` (add auth to scope)
6. Update `STATUS.md` (decisions block, scope table, next steps)
7. Regenerate `backend_implementation.md` prompt (remove auth requirements)

**Result:**
All documents now consistently reflect that auth is out of v0.2.0 and in v0.2.2.

### Example 2: Architectural Decision with Cascade

**User:** `/propagate-decision — Entity backend as foundation`

**Decision:**
```
Decision: Build entity-centric backend first, before other subsystems

Rationale: Core abstraction that everything else depends on

Impact Scope:
- Parallel tracks (reshuffled)
- v0.2.0 vs v0.2.1 scope
- Implementation sequence
- Dependency graph
```

**Cascade Effects:**
- Promoting entity backend to priority
- Deferring API gateway to v0.2.1
- Reordering parallel tracks
- Updating dependency graph

**Documents Affected:**
- Master plan (scope, dependency graph, parallel tracks)
- Entity backend scout (promoted to active)
- API gateway scout (deferred to v0.2.1)
- v0.2.1 master plan (scope increased)
- STATUS.md (decisions, architecture summary)

## Best Practices

1. **Record Verbatim**
   - Capture exact words, not paraphrases
   - Paraphrasing introduces drift and interpretation

2. **Trace Before Editing**
   - Make complete list of dependencies first
   - Prevents missed updates and duplicated effort

3. **Surgical Over Wholesale**
   - Change only affected sections
   - Rewriting entire documents obscures what changed

4. **Always Update STATUS Last**
   - It's the coherence checkpoint
   - If STATUS is current, whole system is current

5. **Document Deferrals Clearly**
   - When work is pushed to later release
   - Explain why and when to reconsider

6. **Verify Cross-References**
   - If doc A says "deferred to X," doc X must acknowledge it
   - No orphaned references

## Quality Checklist

Before marking decision as propagated:

- [ ] Decision recorded at source with human name, date, full reasoning
- [ ] All dependent documents identified
- [ ] Each dependent document updated in specific affected sections
- [ ] STATUS.md reflects all changes
- [ ] Document copies synced across locations (if applicable)
- [ ] No orphaned references to old scope remain
- [ ] Cross-references are consistent
- [ ] Alternatives considered are documented (not just chosen option)

## Troubleshooting

### "I'm not sure what documents are affected"
- Start with obvious ones (master plan, STATUS)
- Use grep to search for keywords
- Check documents that reference the same scope or phase
- When in doubt, include it — better to check and find no changes needed

### "The decision affects too many documents"
- That's normal for architectural decisions
- Make a checklist, work through systematically
- Don't skip documents — propagation must be complete

### "Some documents contradict each other after propagation"
- Review cross-references
- Ensure bidirectional consistency (if A references B, B should acknowledge A)
- Update STATUS.md last to catch inconsistencies

## Related Skills

- `decision-propagation` — Full skill documentation
- `handoff-protocol` — For propagating decisions through handoffs
- `workspace-navigation` — For finding affected documents
