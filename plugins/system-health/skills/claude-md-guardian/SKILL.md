---
name: claude-md-guardian
description: >
  Protect CLAUDE.md files from drift, conflict, and unvalidated modifications
  using hook-based enforcement and periodic audits. Ensures behavioral rules
  remain consistent across global, project, and subdirectory CLAUDE.md files.
  Trigger phrases: "audit CLAUDE.md for conflicts", "protect CLAUDE.md",
  "check CLAUDE.md consistency", "guard agent configuration", "validate
  CLAUDE.md rules", "prevent CLAUDE.md drift", "sync CLAUDE.md files",
  "review behavioral rules for contradictions".
license: proprietary
---

# CLAUDE.md Guardian

## I. Philosophy

CLAUDE.md is the agent's behavioral contract. When rules drift, conflict, or
accumulate without review, agent behavior becomes unpredictable. The guardian
skill treats CLAUDE.md as a living document that requires the same rigor as
source code: validation, consistency checks, and protection against unreviewed
modification.

Three failure modes threaten CLAUDE.md health:
1. **Drift** -- Rules added to one CLAUDE.md but not propagated to related files.
2. **Conflict** -- Contradictory rules across global, project, and subdirectory files.
3. **Bloat** -- Accumulated rules that are no longer relevant or are redundant.

Mechanical enforcement (hooks) prevents unauthorized modification. Periodic
audits catch semantic drift that mechanics cannot detect.

## II. When to Use

- After applying learnings from `reflect-and-learn` to verify no conflicts were introduced.
- During periodic maintenance (weekly or sprint boundaries).
- When agent behavior deviates unexpectedly (first suspect: CLAUDE.md conflict).
- Before onboarding a new team member or agent to a project.
- After merging branches that may have modified CLAUDE.md independently.

Do not use this skill for writing new CLAUDE.md rules (use `reflect-and-learn`
for correction-based rules, or edit directly). Do not use it for auditing
documentation broadly (use `documentation-audit`).

## III. Workflow

**Step 1 -- Inventory all CLAUDE.md files.**

Locate every behavioral configuration file:
- `~/.claude/CLAUDE.md` (global)
- `./CLAUDE.md` (project root)
- `./subdirectory/CLAUDE.md` (subdirectory overrides)
- `./AGENTS.md` (cross-tool compatibility)

**Step 2 -- Extract and normalize rules.**

Parse each file into discrete behavioral rules. Normalize phrasing to detect
semantic duplicates and contradictions. Flag:
- Duplicate rules across files (redundancy)
- Contradictory rules (conflict)
- Rules that reference deprecated tools, paths, or patterns (staleness)

**Step 3 -- Check inheritance hierarchy.**

CLAUDE.md files form a cascade: global < project < subdirectory. Verify:
- Subdirectory rules do not contradict project rules unintentionally
- Project rules do not repeat global rules unnecessarily
- Override intent is explicit, not accidental

**Step 4 -- Configure mechanical protection (optional).**

Set up a PreToolUse hook that intercepts Write/Edit operations targeting
CLAUDE.md files. The hook can:
- Log all modification attempts for audit trail
- Block modifications from sub-agents (only primary agent may modify)
- Require a specific confirmation pattern before allowing changes

**Step 5 -- Report findings.**

Produce a health report listing:
- Total rule count per file
- Conflicts found (with file locations and rule text)
- Redundancies identified
- Staleness candidates
- Recommended actions (merge, delete, promote, demote)

## IV. Best Practices

- Run the guardian after every `reflect-and-learn` session.
- Keep global CLAUDE.md under 50 rules. Overflow to project-level files.
- Use explicit override markers when subdirectory rules intentionally contradict
  project rules ("OVERRIDE: ...").
- Version CLAUDE.md in git to track rule evolution over time.
- Cross-reference CLAUDE.md rules with AGENTS.md for cross-tool consistency.

## V. Quality Checklist

- [ ] All CLAUDE.md files inventoried (global, project, subdirectory)
- [ ] No unintentional contradictions between hierarchy levels
- [ ] Redundant rules identified and consolidated
- [ ] Stale rules flagged for removal
- [ ] Mechanical protection hook installed (if appropriate)
- [ ] Health report generated with actionable recommendations

## VI. Common Pitfalls

- **Treating all contradictions as bugs.** Some subdirectory overrides are intentional.
- **Over-guarding.** Blocking all CLAUDE.md modifications prevents legitimate learning.
- **Ignoring AGENTS.md.** Cross-tool files can contradict CLAUDE.md silently.
- **Manual-only audits.** Without hooks, modifications between audits go undetected.
- **Rule count as quality metric.** More rules does not mean better behavior.

## VII. Related Skills

- `reflect-and-learn` -- Applies learnings that this skill then validates
- `documentation-audit` -- Broader documentation health (not CLAUDE.md-specific)
- `hooks-reference` -- Configure the mechanical protection hooks
- `health-audit` -- Repository-wide health check (includes CLAUDE.md as one dimension)
