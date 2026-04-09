---
name: hooks-reference
model: sonnet
description: Produces a hook script scaffold and settings.json registration block by looking up the correct lifecycle event, exit code pattern, and configuration for a Claude Code hook. Use when: "write a new hook", "hook is not firing", "block a tool call mechanically", "configure sub-agent coordination", "implement a security block pattern".
license: proprietary
category: system-health
---

# Hooks Reference

## I. Philosophy

Hooks are the mechanical enforcement layer of agent safety and observability.
Unlike CLAUDE.md instructions, which guide agent behavior through documentation,
hooks execute code at lifecycle boundaries where the agent cannot override them.
A well-designed hook system makes dangerous operations impossible rather than
merely discouraged.

This skill is a reference card, not a tutorial. It assumes you know what hooks
are and need to quickly find the right event, the right exit code, or the right
configuration pattern. For architectural understanding, read the
`seed_hooks_lifecycle_mastery` and `seed_mechanical_safety_enforcement` seeds.

## II. When to Use

- Writing a new hook and need to know which event type to target.
- Debugging why a hook is not firing (wrong event name, wrong exit code).
- Reviewing the full lifecycle to understand execution order.
- Implementing a security block pattern (exit code 2).
- Configuring hooks in `.claude/settings.json`.
- Building sub-agent coordination via SubagentStart/SubagentStop hooks.

Do not use this skill for designing observability dashboards (use
`observability-dashboard` instead) or for understanding the correction-capture
pipeline (use `reflect-and-learn` instead).

## III. Workflow

**Step 1 -- Identify the lifecycle stage.**

Determine where in the agent lifecycle you need to intercept. The 13 events
fall into 5 categories:

| Category | Events | Purpose |
|----------|--------|---------|
| Session | Setup, SessionStart, SessionEnd | Initialization and cleanup |
| User | UserPromptSubmit, Notification | Input interception |
| Tool | PreToolUse, PostToolUse, PostToolUseFailure, PermissionRequest | Execution guard |
| SubAgent | SubagentStart, SubagentStop | Multi-agent coordination |
| Context | PreCompact, Stop | Memory and completion |

**Step 2 -- Choose the enforcement pattern.**

- **Block** (exit code 2): Tool call is halted. Error message shown to agent.
  Use for security-critical interception in PreToolUse.
- **Observe** (exit code 0): Event is logged but execution continues.
  Use for PostToolUse, Stop, SessionEnd capture.
- **Modify** (stdout JSON): Hook output can provide data back to the agent.
  Use for UserPromptSubmit transformation or PreCompact custom instructions.

**Step 3 -- Write the hook script.**

UV single-file Python scripts with embedded dependencies:

```python
# /// script
# dependencies = ["requests"]
# ///
import json, sys

event = json.loads(sys.stdin.read())
# ... process event ...
# Exit 0 to allow, Exit 2 to block
```

**Step 4 -- Register in settings.json.**

Add the hook to `.claude/settings.json` under the `hooks` key, mapping the
event name to the script path.

**Step 5 -- Test the hook.**

Run a session that triggers the target event. Verify the hook fires by checking
its side effects (log file, HTTP POST, blocked operation).

## IV. Best Practices

- Keep PreToolUse hooks fast. They fire on every tool invocation.
- Use UV single-file scripts to avoid polluting project dependencies.
- Store hooks in `.claude/hooks/` with subdirectories per event type.
- Test exit code 2 blocks explicitly -- verify the tool call is actually halted.
- Guard against infinite loops in Stop hooks (`stop_hook_active` flag).
- Log hook execution failures separately from hook-captured events.

## V. Quality Checklist

- [ ] Hook targets the correct lifecycle event
- [ ] Exit code matches intent (0 = observe, 2 = block)
- [ ] Script is idempotent (safe to re-execute)
- [ ] Performance impact is acceptable for hot-path hooks (PreToolUse)
- [ ] Hook is registered in `.claude/settings.json`
- [ ] Tested with a real agent session, not just unit tests

## VI. Common Pitfalls

- **Wrong event name.** "pre_tool_use" vs "PreToolUse" -- case and format matter.
- **Missing stdin read.** Hooks receive event data on stdin as JSON.
- **Heavy dependencies in PreToolUse.** A 2-second import delays every tool call.
- **No guard in Stop hooks.** Without `stop_hook_active`, Stop hooks can trigger
  themselves recursively.
- **Assuming hooks survive compaction.** Hook scripts persist, but the context
  that configured them may compact away. Use Setup hooks for re-initialization.

## VII. Related Skills

- `observability-dashboard` -- Visualize events captured by hooks
- `tool-intercept-logger` -- OTEL-compatible tool call logging
- `claude-md-guardian` -- Protect CLAUDE.md via hook enforcement
- `agent-performance-report` -- Aggregate hook data into performance metrics

## Output
- A UV single-file Python hook script (with embedded dependency declarations) ready to drop into `.claude/hooks/{event-type}/`.
- A `settings.json` snippet registering the hook under the correct event key.
- Exit code guidance specific to the chosen enforcement pattern (0 = observe, 2 = block).

## Examples
**Scenario 1:** "I want to block sub-agents from writing to CLAUDE.md" → PreToolUse hook targeting Write/Edit operations on CLAUDE.md paths. Script exits 2 when the tool name matches and the path contains "CLAUDE.md". Settings.json snippet provided.
**Scenario 2:** "Log every tool call to a file for debugging" → PostToolUse hook (exit 0) that appends tool_name, duration_ms, and status to `.claude/hooks/tool-log.jsonl`. No blocking behavior.

## Edge Cases
- Stop hooks that trigger agent re-runs must set a `stop_hook_active` guard to prevent infinite recursion — always include this guard when writing Stop hooks.
- If a PreToolUse hook has heavy imports, move them inside the function or use lazy loading — a 2-second import delays every tool call.

## Anti-Patterns
- Using the wrong event name casing ("pre_tool_use" instead of "PreToolUse") — the hook will silently never fire.
- Assuming hooks survive context compaction — use Setup hooks for re-initialization rather than relying on context that may have been compacted away.
