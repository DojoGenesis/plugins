---
name: convergence-checker
version: "1.0.0"
model: sonnet
description: "Runs a convergence gate: counts dirty files, sessions since last convergence, open items, and produces a triage report with RED/YELLOW/GREEN status. Use when: 'converge', 'convergence check', 'drift check', 'am I drifting'."
triggers:
  - "converge"
  - "convergence check"
  - "drift check"
  - "am I drifting"
category: dojo-craft

inputs:
  - name: trigger_reason
    type: string
    description: Why convergence is being run — manual call, drift warning, pre-sprint, or post-merge
    required: false
outputs:
  - name: convergence_report
    type: ref
    format: markdown
    description: Convergence report with status color, dirty file inventory, triage list, and recommended actions; ledger entry updated
---

# Convergence Checker Skill

## I. Philosophy

Sonnet sessions produce excellent artifacts but poor trajectory. Each session is locally optimal — clean build, tests pass, feature shipped — but globally drifting: more open items, more uncommitted state, more deferred validation. The missing discipline is periodic evaluation of trajectory, not just output.

Convergence is not a feature session. It produces no new features. It produces a clean, tested, committed, evaluated state — and a reset counter so the next cycle starts from solid ground.

The drift thresholds are intentionally conservative. YELLOW fires at 10 dirty files or 4 sessions — not because the project is in trouble at that point, but because that is when intervention is cheap. RED is expensive. YELLOW is the efficient intervention point.

Do not skip convergence because "things are going well." Drift is invisible until it is expensive.

## II. When to Use

- When `drift-detector.sh` fires a YELLOW warning (10+ dirty files OR 4+ sessions since last convergence)
- When `drift-detector.sh` fires a RED warning (25+ dirty files OR 6+ sessions)
- Before dispatching a large parallel agent swarm — convergence ensures the baseline is clean
- After a multi-session sprint to consolidate before the next phase
- When you sense accumulating open items but cannot articulate the current priority

Do not use this skill for feature work. Convergence sessions produce zero new features. Any fix discovered during convergence is logged and deferred — never implemented in-session.

## III. Workflow

### Step 1: MEASURE

Establish the current quantitative state.

Run the following:

```bash
# Count uncommitted changes per repo
git status --short | wc -l

# List all uncommitted files
git status --short

# Count untracked files separately
git status --short | grep "^?" | wc -l

# Check for sub-repos with dirty state
find . -name ".git" -maxdepth 3 -type d | while read gitdir; do
  repo=$(dirname "$gitdir")
  count=$(git -C "$repo" status --short 2>/dev/null | wc -l | tr -d ' ')
  if [ "$count" -gt "0" ]; then
    echo "$repo: $count dirty files"
  fi
done
```

Read `~/.claude/convergence-ledger.md` to find:
- Date of last convergence
- Session count since last convergence
- Any items deferred from the prior convergence

If the ledger does not exist, create it with today as the baseline. Session count starts at 0.

### Step 2: THRESHOLD

Apply drift thresholds to determine status.

| Status | Condition | Meaning |
|--------|-----------|---------|
| GREEN | <10 dirty files AND <4 sessions | Healthy. Convergence optional. |
| YELLOW | 10-24 dirty files OR 4-5 sessions | Warning. Converge before next sprint. |
| RED | 25+ dirty files OR 6+ sessions | Critical. Converge before any new work. |

Either condition triggers the higher status. A project with 3 dirty files but 6 sessions since last convergence is RED.

Print the status color prominently at the top of the report.

### Step 3: INVENTORY

List all uncommitted changes grouped by repo/directory.

For each dirty file:
- Full path
- Git status code (M = modified, A = added, D = deleted, ? = untracked, R = renamed)
- A brief guess at what the change represents (based on file name and path)

Group by repo. In a monorepo with sub-repos, each sub-repo is an independent convergence unit.

Example output:
```
AgenticGatewayByDojoGenesis/ (8 dirty files)
  M  server/database/handle_documents.go
  M  server/database/rag.go
  ?? server/database/handle_documents_test.go
  ...

CoworkPluginsByDojoGenesis/ (4 dirty files)
  M  plugins/dojo-craft/skills/adr-writer/SKILL.md
  ...
```

### Step 4: TRIAGE

For each dirty file, assign a disposition.

Disposition options:
- **COMMIT** — Change is complete, tests pass (or can pass), ready to commit. Identify the commit message.
- **STASH** — Work in progress, not ready to commit but worth keeping. Name the WIP context.
- **DISCARD** — Abandoned work, wrong direction, or superseded. Confirm before discarding.
- **DEFER** — Blocked by something external. Name the blocker explicitly.

The triage IS the work of convergence. Do not treat it as overhead.

For COMMIT items:
- Run `go build ./...` and `go test ./...` before marking any Go file as ready to commit
- Run `tsc --noEmit` before marking any TypeScript file as ready to commit
- A file that fails build is DEFER, not COMMIT

For STASH items:
- Name what needs to happen before the item can be committed
- Note whether a parallel agent could complete it

For DISCARD items:
- Do not discard without explicit confirmation. State the reason for discard.
- If in doubt, DEFER rather than DISCARD.

### Step 5: OPEN-ITEMS

Survey open items across project tracking files.

Check:
- CLAUDE.md "Open Items" section
- MEMORY.md open items
- Any active TODO.md files
- `grep -r "TODO\|FIXME\|HACK\|XXX" --include="*.go" --include="*.ts" . | head -20` — code-embedded markers

For each open item, assign:
- **Next session** — high priority, unblocked, clear definition of done
- **Parking lot** — valid but not urgent; review at next convergence
- **Kill** — no longer relevant, superseded, or too speculative to act on

The triage list is written back to the tracking file at the end of the session.

### Step 6: REPORT

Produce the convergence report.

```
# Convergence Report
**Date:** YYYY-MM-DD
**Status:** GREEN | YELLOW | RED
**Trigger:** [manual / drift-detector / pre-sprint / post-merge]

## Metrics
- Dirty files: N (across N repos)
- Sessions since last convergence: N
- Last convergence: YYYY-MM-DD

## Status: [COLOR]
[One sentence on why this status was assigned.]

## Dirty File Inventory
[Grouped by repo, with disposition for each file]

## Triage Summary
- COMMIT: N files (N commits ready)
- STASH: N files (N WIP items)
- DISCARD: N files (pending confirmation)
- DEFER: N files (N blockers)

## Open Items Triage
- Next session: N items
  [List]
- Parking lot: N items
  [List]
- Kill: N items
  [List]

## Recommended Actions
1. [Most urgent specific action]
2. [Second action]
3. [Third action]

## Blockers
[List of items that must be resolved before convergence completes]
```

### Step 7: LEDGER

Update `~/.claude/convergence-ledger.md` with the session outcome.

Ledger entry format:
```
## YYYY-MM-DD — [Status Color]
- Dirty files at start: N
- Sessions consumed: N
- Commits produced: N
- Items triaged: N (next: N, parking: N, killed: N)
- Blockers: [list or "none"]
- Session count reset to: 0
- Notes: [one sentence on key finding]
```

If the ledger does not exist, create it. The first entry is the baseline.

## IV. Quality Checklist

- [ ] Measured dirty file count and session count from actual `git status` and ledger
- [ ] Status color assigned using threshold table (not judgment)
- [ ] Every dirty file assigned a disposition (COMMIT/STASH/DISCARD/DEFER)
- [ ] Go files marked COMMIT have passed `go build ./...` and `go test ./...`
- [ ] Open items surveyed from CLAUDE.md, MEMORY.md, and code markers
- [ ] All open items assigned a disposition (next/parking/kill)
- [ ] Report written with status color prominent
- [ ] Ledger updated with entry and session count reset

## V. Common Pitfalls

- **Marking files COMMIT without running the build gate.** A clean `git status` achieved by committing broken code is not convergence. Run `go build ./...` before any Go file becomes a commit candidate.
- **Treating convergence as optional when status is YELLOW.** YELLOW is the efficient intervention point. Waiting for RED means the triage is 3x harder and the risk of a broken baseline is real.
- **Discarding files without confirmation.** DISCARD is irreversible. Always state the reason and get confirmation before executing.
- **Skipping the open items triage.** Uncommitted code is visible in `git status`. Drifting open items are invisible. The open items triage is the highest-leverage work in the session.
- **Force-committing to clear the count.** A file that does not pass build is not COMMIT. Document it as DEFER with the blocker named.
- **Running convergence mid-feature.** Convergence at a natural session boundary. If you are mid-task, finish the task or stage it explicitly, then converge.

## VI. Related Skills

- `claude-md-guardian` — Pairs well as Phase 5 of a full convergence: after committing code, audit the behavioral contract
- `adr-writer` — If a DEFER item reveals an unresolved architectural question, write an ADR before the next session
- `convergence-gate` (system-health plugin) — The full 7-phase convergence procedure; this skill focuses on the drift assessment and triage phases

## VII. Output

- Convergence report with status color, inventory, triage dispositions, open items triage, and recommended actions
- Updated `~/.claude/convergence-ledger.md` with entry and reset session count
- Explicit list of commits ready to execute (for COMMIT items)
- Explicit list of blockers preventing full convergence

## Examples

**Scenario 1:** Status YELLOW — 14 dirty files, 4 sessions.

Measured: 14 dirty files across 2 repos, 4 sessions since last convergence on Apr 12. Status: YELLOW. Inventory: 8 files in Gateway (5 COMMIT, 2 STASH, 1 DEFER — failing test), 6 files in plugins (4 COMMIT, 2 STASH). Open items: 7 total, 3 to next session, 3 to parking lot, 1 killed (superseded). Ledger updated, counter reset to 0. Recommended actions: (1) commit 9 COMMIT files across 3 conventional commits, (2) log Gateway test failure as DEFER with root cause noted, (3) kick off next session from clean baseline.

**Scenario 2:** Status RED — 31 dirty files, 6 sessions.

Measured: 31 dirty files across 4 repos, 6 sessions. Status: RED. Inventory reveals 12 files are untracked documentation, 10 are complete WIP in Gateway, 9 are abandoned experiments. Triage: 10 COMMIT, 9 STASH (one agent needed to complete), 12 DISCARD (pending confirmation). Open items: 18 total; 6 killed on review. Blockers: 2 DEFER items blocked by Gateway D1Syncer injection (not resolved in this session). Ledger updated, counter reset to 0. Key finding: bloat from abandoned experiments was the primary driver of RED status, not active WIP.

## Edge Cases

- If the convergence ledger does not exist, create it with today's date as the baseline entry. Session count starts fresh from 0.
- If a sub-repo has its own `.git`, treat it as an independent convergence unit. Its dirty files are counted separately and committed from within that repo's context.
- If convergence reveals that the current trajectory is fundamentally wrong (not just drifted), flag this explicitly in the report and recommend pausing new work until the strategic question is resolved. This is a CRITICAL finding, not just a WARNING.
- If status is GREEN and the user ran this manually, report the green status and confirm no action is required. Do not invent work.

## Anti-Patterns

- **"Just one quick fix while I'm here"** — Convergence is not a feature session. Any discovered fix is logged and deferred. Implementing it during convergence adds new state while settling existing state.
- **Convergence as a checkbox** — The goal is a clean, committed, evaluated baseline — not a completed checklist. If the triage reveals 10 items that cannot be committed cleanly, the right outcome is a well-documented set of DEFER items, not force-commits.
- **Treating convergence as punishment for drift** — Convergence is a tool for staying fast. The teams that converge regularly ship more, not less. The cost is 30-60 minutes per cycle; the benefit is avoiding days of untangling later.
- **Skipping the ledger update** — Without a ledger update, the session counter never resets and the drift detector will immediately re-fire YELLOW on the next session. The ledger is the mechanism, not optional bookkeeping.
