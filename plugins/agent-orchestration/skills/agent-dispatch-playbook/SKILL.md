---
name: agent-dispatch-playbook
description: Concrete patterns for orchestrating parallel agent work — worktree isolation, background delegation, fix agents, audit agents. Use when dispatching multiple agents, planning parallel tracks, or deciding foreground vs background execution.
triggers:
  - "dispatch agents in parallel"
  - "orchestrate parallel work across repos"
  - "plan agent delegation strategy"
metadata:
  version: "1.0"
  created: "2026-04-07"
  author: "Tres Pies Design"
  tool_dependencies: ["Agent", "Bash", "TodoWrite"]
  portable: true
  tier: 1
  agents: ["agent-orchestration"]
---

# Agent Dispatch Playbook

## I. Philosophy

Agent orchestration is not about launching as many agents as possible — it's about matching the **isolation model** to the **dependency graph**. Today's session (Apr 7, 2026) dispatched 15 agents across 7 repos, completing in hours what would take days sequentially. The patterns below are extracted from that lived experience, not theory.

The core insight: **the main thread is for strategy, agents are for heavy lifting.** The main thread reads results, makes judgment calls, resolves conflicts, and sequences dependent work. Agents do the grunt work in parallel.

## II. When to Use

- Multi-repo changes that touch independent file sets
- Health audits, documentation refreshes, or test fixes across repos
- Any task that decomposes into 2+ independent tracks
- When you need to verify work before proceeding to the next phase

## III. The Five Dispatch Patterns

### Pattern 1: Parallel Execution Tracks (Worktree Isolation)

**When:** Multiple code changes in the SAME repo that touch DIFFERENT packages/directories.

**How:**
- Launch each track as an Agent with `isolation: "worktree"`
- Each gets its own git branch in `.claude/worktrees/`
- Tracks MUST touch non-overlapping files
- After completion, merge worktree branches into main

**Example from today:** Gateway Track 2 (workflow/executor.go, channel/nats_bus.go) and Track 3 (server/handle_websocket.go) ran in parallel worktrees — different packages, clean merge.

**Gotcha:** Worktree changes are uncommitted by default. You must copy files to main and manually apply shared-file changes (server.go, router.go) if both tracks modify them.

```
Agent(isolation="worktree", prompt="Track A: modify workflow/ and channel/")
Agent(isolation="worktree", prompt="Track B: modify server/ only")
# After both complete:
# 1. Copy new files from worktrees to main
# 2. Cherry-pick shared-file edits manually
# 3. Verify: go build ./... && go test ./...
```

### Pattern 2: Cross-Repo Parallel (Background Agents)

**When:** Changes in DIFFERENT repos with zero dependencies between them.

**How:**
- Launch all agents with `run_in_background: true`
- Each agent works in its own repo directory — no isolation needed
- Main thread continues with non-overlapping work
- Results arrive as task notifications

**Example from today:** HTMLCraft integration (TypeScript) ran alongside Gateway workflow wiring (Go) — completely independent repos.

```
Agent(prompt="Fix tests in repo A", run_in_background=true)
Agent(prompt="Fix tests in repo B", run_in_background=true)
Agent(prompt="Add feature in repo C", run_in_background=true)
# Main thread: update documentation or plan while waiting
```

### Pattern 3: Audit Swarm (Read-Only Parallel)

**When:** Gathering information across multiple repos without making changes.

**How:**
- Launch 2-4 audit agents in background, each with a different scope
- Agents READ and REPORT but don't modify files (or save reports to non-overlapping paths)
- Main thread compiles the unified report from all agent results

**Example from today:** 3 health audit agents (Gateway, 4 smaller repos, HTMLCraft) ran simultaneously. Each produced findings; main thread compiled the unified scorecard.

**Scaling rule:** 3 concurrent audit agents is the sweet spot. More than 4 starts hitting diminishing returns from context overhead.

```
Agent(subagent_type="health-auditor", prompt="Audit repo A", run_in_background=true)
Agent(subagent_type="health-auditor", prompt="Audit repo B+C+D", run_in_background=true)
Agent(subagent_type="health-auditor", prompt="Audit repo E", run_in_background=true)
# Wait for all 3, then compile unified report
```

### Pattern 4: Sequential Fix Agent

**When:** Fixing issues that were discovered by an audit, where fixes have dependencies.

**How:**
- Run in foreground (not background) because you need the result before proceeding
- Give the agent the EXACT findings from the audit (file paths, line numbers, expected values)
- Verify the fix with build/test before moving to the next dependent task

**Example from today:** After audit found 19 SKILL.md files missing triggers, a single fix agent updated all 19 + verified `go test ./tests/skills/...` passed.

**Key principle:** Fix agents get specific instructions, not open-ended research tasks. The audit already did the research — the fix agent just executes.

```
# BAD: "Find and fix test failures" (too open-ended)
# GOOD: "Update loader_test.go line 163: change 15 to 31. Update line 357: change 'debugging' to 'debugging-troubleshooting'. Verify: go test ./internal/skills/..."
```

### Pattern 5: Phased Pipeline (Blocker → Parallel → Verify)

**When:** Some work must complete before parallel work can begin.

**How:**
1. **Phase A:** Fix blockers in foreground (build errors, missing deps)
2. **Phase B:** Launch parallel agents for independent tracks
3. **Phase C:** Merge results, verify combined build
4. **Phase D:** Launch dependent work (things that needed Phase B outputs)

**Example from today:**
- Phase A: Fix 4 duplicate method build errors (foreground, 5 min)
- Phase B: Launch 3 parallel agents (workflow wiring, WebSocket hub, HTMLCraft integration)
- Phase C: Copy worktree files, verify `go build && go test` (foreground)
- Phase D: Push to DojoGenesis, run health audits

```
# Phase A — foreground, blocks everything
fix_build_errors()
verify_build()

# Phase B — parallel, independent
Agent("Track 2: workflow", isolation="worktree", run_in_background=true)
Agent("Track 3: websocket", isolation="worktree", run_in_background=true)
Agent("Track 4: htmlcraft", run_in_background=true)

# Phase C — after all Phase B agents complete
merge_worktrees()
verify_combined_build()

# Phase D — depends on Phase C
push_to_remotes()
run_health_audits()
```

## IV. Decision Matrix

| Situation | Pattern | Isolation | Background? |
|-----------|---------|-----------|-------------|
| 2+ changes in same repo, different dirs | Worktree Tracks | worktree | Yes |
| Changes across different repos | Cross-Repo Parallel | none | Yes |
| Read-only audits across repos | Audit Swarm | none | Yes |
| Fixing specific known issues | Sequential Fix | none | No (foreground) |
| Mix of blocking + parallel work | Phased Pipeline | mixed | Mixed |

## V. Prompt Engineering for Agents

### What makes a good agent prompt:
1. **State the goal** in the first line
2. **List exact file paths** the agent should modify
3. **Specify the verification command** (`go test ./...`, `npm test`, etc.)
4. **Name what NOT to touch** (prevents overlap with other agents)
5. **Include the commit message** if the agent should commit

### What makes a bad agent prompt:
- "Based on your findings, fix the bug" — pushes synthesis onto the agent
- "Investigate and implement" — two different tasks crammed together
- Omitting file paths — agent wastes time exploring
- Not specifying verification — agent can't confirm its own work

## VI. Model Routing

| Task Type | Model | Why |
|-----------|-------|-----|
| Planning, judgment, architecture | Opus | Needs reasoning depth |
| Parsing, sed, template application | Sonnet | Fast, mechanical work |
| Health audits, code exploration | Opus or Sonnet | Depends on codebase familiarity |
| Fix agents with exact instructions | Sonnet | Instructions are complete, just execute |

**Rule of thumb:** If the prompt contains all file paths and exact changes, use Sonnet. If the agent needs to make judgment calls, use Opus.

## VII. Anti-Patterns

1. **Launching agents for trivial tasks** — If it's a single `sed` command or one file edit, just do it in the main thread.
2. **Duplicating work** — If you delegate research to an agent, don't also search the same files yourself.
3. **More than 4 parallel agents** — Diminishing returns. 3 is the sweet spot.
4. **Worktrees for shared files** — If two tracks both need to modify `server.go`, don't use worktrees. Do one track, then the other, or split the file changes.
5. **Background agents for blocking work** — If you need the result before proceeding, run foreground.

## VIII. Metrics from April 7, 2026 Session

| Metric | Value |
|--------|-------|
| Total agents dispatched | 15 |
| Max concurrent agents | 3 |
| Execution tracks (worktree) | 2 |
| Cross-repo parallel agents | 4 |
| Audit swarm agents | 3 |
| Fix agents | 4 |
| Documentation agents | 4 |
| Repos touched | 7 |
| Files modified | 500+ |
| New tests added | 78 |
| Time saved (estimated) | 3-4x vs sequential |
