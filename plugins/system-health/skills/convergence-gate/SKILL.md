---
name: convergence-gate
model: opus
description: Runs a structured 5-phase convergence session to arrest strategic drift after 3-4 Sonnet feature sessions. Use when the drift-detector fires YELLOW or RED, or when you notice accumulating uncommitted state, deferred validations, and growing open-items lists.
category: system-health
version: 1.0.0
tags: [convergence, drift, hygiene, governance]

inputs:
  - name: trigger_reason
    type: string
    description: Why convergence is being run — YELLOW drift warning, RED drift warning, or manual call
    required: false
outputs:
  - name: convergence_report
    type: ref
    format: markdown
    description: Updated convergence ledger entry with session count reset, commit sweep results, triage decisions, and strategic evaluation
---

# Convergence Gate Skill

## Philosophy

Sonnet sessions produce excellent artifacts but poor trajectory. Each session is locally optimal — clean build, tests pass, seed captured — but globally drifting: more open items, more uncommitted state, more deferred validation. The missing discipline is periodic evaluation of trajectory, not just output.

Convergence is not a feature session. It produces no new features. It produces a clean, tested, committed, evaluated state — and a reset counter so the next cycle starts from solid ground.

The drift-detector.sh hook enforces this mechanically, but the convergence gate skill is the procedure that actually runs when the hook fires.

## When to Use

- When `drift-detector.sh` fires a **YELLOW warning** (10+ dirty files OR 4+ sessions since last convergence)
- When `drift-detector.sh` fires a **RED warning** (25+ dirty files OR 6+ sessions)
- When open-items lists have been growing across multiple sessions without resolution
- When multiple deferred validations (tests, build checks, config audits) have accumulated
- When you sense "things are going well" but can't clearly articulate what the next priority is — that ambiguity is exactly what convergence resolves

Do not use this skill for feature work. Convergence sessions produce zero new features. Any fix discovered during convergence is logged and deferred — never implemented in-session.

## Workflow

### Phase 1: Inventory

**Objective:** Establish a complete picture of the current state before touching anything.

1. Run `git status` across all active repos to count dirty files and identify untracked paths.
2. Read `~/.claude/convergence-ledger.md` to confirm session count since last convergence.
3. Identify the drift severity: YELLOW (10+ files or 4+ sessions) or RED (25+ files or 6+ sessions).
4. List all open items from CLAUDE.md, MEMORY.md, and any active TODO files — do not edit them yet.
5. Identify deferred validations: any `go build`, `go test`, migration checks, or connectivity tests that were skipped in prior sessions.

Output of Phase 1: a flat inventory list. No judgments or actions yet.

### Phase 2: Commit Sweep

**Objective:** Commit all work-in-progress that is ready to ship.

1. For each dirty repo, determine if the changes are shippable (build passes, tests pass, intent clear).
2. Run `go build ./...` and `go test ./...` before staging any Go files.
3. Commit shippable changes with conventional commit messages (`feat:`, `fix:`, `chore:`, `docs:`).
4. For changes that are NOT shippable, document the blocker in the convergence ledger and leave them staged or unstaged — do not force-commit broken state.
5. After all commits land, confirm `git status` is clean (or explains each remaining dirty file).

### Phase 3: Deferred Validations

**Objective:** Run every validation that was skipped or deferred in previous sessions.

1. Execute each deferred check from the Phase 1 inventory.
2. For each validation:
   - **Pass:** note it in the ledger and close the deferred item.
   - **Fail:** document the failure, its probable root cause, and the specific fix needed — but do NOT implement the fix in this session.
3. Config checks take priority: scan `settings.json`, `.env`, `wrangler.toml`, and any gateway config for stale URLs or missing keys before debugging any code.
4. MCP server connectivity: verify each configured server responds before reporting any MCP tool as broken.

### Phase 4: Open Items Triage

**Objective:** Decide the fate of every open item — resolve, defer, or kill.

1. Read through the accumulated open items list from Phase 1.
2. For each item, assign one of three dispositions:
   - **Next session:** high priority, unblocked, clear definition of done.
   - **Parking lot:** valid but not urgent; survives to next convergence review.
   - **Kill:** no longer relevant, superseded, or too speculative to act on — remove it.
3. Write the triaged list back to the appropriate tracking file (CLAUDE.md open items section, MEMORY.md, or a project-specific file).
4. The triage IS the work. Do not treat it as overhead.

### Phase 5: Strategic Evaluation

**Objective:** Assess whether the current trajectory will produce the desired outcome.

1. Review the last 3-4 session summaries or compression logs.
2. Ask: What was the stated goal at the start of this cycle? What actually happened?
3. Identify any drift between stated priorities and actual work done.
4. Produce a one-paragraph trajectory assessment: is the current approach correct, or does direction need adjustment?
5. Update the convergence ledger with: date, session count consumed, disposition of open items, strategic assessment, and any architectural concerns.
6. Reset the session counter in the ledger.

## Output

- Updated `~/.claude/convergence-ledger.md` with: date, session count reset, commit sweep results (N commits), validation outcomes, triage decisions (X to next, Y to parking lot, Z killed), and strategic assessment.
- All repos in a clean or explicitly-documented state.
- Triaged open items list written back to tracking files.
- No new features introduced.

## Examples

**Example 1: YELLOW drift, 12 dirty files, 4 sessions**

drift-detector fires YELLOW mid-session. Phase 1 inventory finds: 12 dirty files across Gateway and CLI repos, 4 sessions logged. Phase 2 commits 8 files across 3 conventional commits; 4 files blocked by a failing test in `handle_documents_test.go` — documented, left staged. Phase 3 runs deferred `go test ./...` in Gateway; 2 tests fail; root cause logged (nil D1Syncer injection). Phase 4 trots through 11 open items: 4 to next session, 5 to parking lot, 2 killed (superseded by Wave 2C work). Phase 5 assessment: "Wave 2C RAG track is on schedule but D1Syncer injection is the only remaining blocker — resolve before any other Gateway work." Ledger updated, counter reset to 0.

**Example 2: RED drift, manual trigger before a major integration sprint**

User runs `/converge` manually before dispatching 6 parallel agents for Era 4 Phase 1. Phase 1 inventory: 27 dirty files, 6 sessions. Severity RED. Phase 2 commit sweep commits 19 files; 8 held back (incomplete RAG implementation — not shippable). Phase 3 deferred validations: `go build ./...` passes, but `wrangler.toml` has stale Gateway URL (was `localhost:8080`, should be `localhost:7340`) — config bug caught before 6-agent dispatch that would have all failed at the connectivity check. Phase 4: 18 open items triaged. Phase 5 assessment: "Integration sprint is safe to proceed — all parallel tracks have clean build gates; stale config corrected." Ledger reset.

## Edge Cases

- If the convergence ledger does not exist at `~/.claude/convergence-ledger.md`, create it with today's date as the baseline entry before running any phases.
- If a commit sweep produces a pre-commit hook failure, fix the hook violation and retry — do not use `--no-verify`. The failed commit still counts as a deferred validation; log it.
- If Phase 5 strategic evaluation reveals the current trajectory is fundamentally wrong (not just drifted), escalate: stop the convergence session, surface the misalignment explicitly, and do not resume feature work until the strategic question is resolved.
- If drift is RED and the repo is a sub-repo with its own `.git`, treat it as an independent convergence unit — commit sweeps and validations run inside that repo's context, not the parent monorepo.

## Anti-Patterns

- **"Just one quick fix while I'm here"** — Convergence is not a feature session. Any discovered fix is logged and deferred. Implementing it during convergence defeats the purpose: you add new state while trying to settle existing state.
- **Skipping Phase 4 triage because "it's not code work"** — The open items triage is the highest-leverage work in the entire session. Deferred decisions compound faster than deferred code.
- **Treating convergence as optional when things are going well** — Drift is invisible until it is expensive. YELLOW is the time to converge, not when you hit RED with a broken build the day before a deadline.
- **Force-committing broken state to clear the dirty file count** — A clean `git status` achieved by committing broken code is not convergence; it is disguised debt. Document the blocker; leave the files unstaged.
- **Running convergence in the middle of a half-finished feature** — Convergence should happen at natural session boundaries. If you are mid-task, finish the task (or stage the work-in-progress explicitly), then converge.
