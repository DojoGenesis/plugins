---
name: dag-plan
description: "Use when you are about to split a goal into parallel tracks or agents: how to cut tracks by decisions, check the fan-out is real, and report returns instead of dispatches."
model: inherit
category: dispatch-coordinate
---

# Cutting a goal into tracks

Parallel work only pays if the tracks are independent. This is how to cut them, and how to check the cut before any model runs. `/dojo-flow:build` and `/dojo-flow:converge` run the result.

## 1. Cut by decisions, not only by files

Two tracks with different files can still depend on each other. They couple on **decisions**: a function name one track picks and the other calls, a JSON shape, a config key, a file name, an agreed value. Independent agents guess each other's names and ship dead links.

For every pair of tracks, ask: does either one consume what the other produces, or read something the other settles? If yes, either merge the two tracks or put one first. The `/dojo-flow:build` workflow cannot put one first: it starts every track at once, so merge them, or run the earlier track as its own build and the later one as a second build.

Then write the shared decisions into a contract file before anything fans out, and hand its text to every track. The build workflow does this in its Contract phase; by hand, it is a file with the names, shapes, and interfaces everyone may assume.

## 2. Check the fan-out is real

Write the tracks as `[{name, files, deps?}]` and run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dag_ops.py" tracks --json '<the tracks as JSON>'
```

- It exits 1 and says why if two tracks claim overlapping files (a directory covers everything under it), a name repeats, or a path has a glob or `..`.
- `width` is how many tracks can run side by side. If it is below the track count, part of your fan-out is a chain, and the build workflow will not order it for you.
- `critical_path` is the longest chain: more workers do not shorten it.

For a bigger graph, `width`, `critical-path`, `cone NODE`, `reduce` and `validate` take `{"nodes": [...], "edges": [[from, to]]}`.

## 3. Ownership is taught here, not enforced

Give each track files no other track writes, say so in its prompt, and compare the changed files with the map afterwards. The workflow audit does that comparison and reports a difference. Nothing blocks a write, so a prompt is a request, not a lock. Where an agent could do real harm, remove the capability (read-only tools, no git) instead of adding a warning.

## 4. Keep small fixes small

A fix under ten lines in one file stays in your main session. Spawning an agent for it costs more than doing it, and it hides the change from you.

## 5. Count returns, not dispatches

When you summarize a fan-out, say three numbers: dispatched, returned, failed. A dead reviewer looks exactly like a clean one. If returned is below dispatched, the run is incomplete: say which ones died and re-run only those, as a fresh run.

An agent's own "done" or "tests pass" is a claim. Run the check yourself in this session and show its result before you say done.

## 6. Match the fan-out to the machine

A track that needs exclusive use of something (a simulator, a device, the display, a fixed port) starves when many agents share the machine. Run those tracks alone, after the others. Treat "could not verify" as a legitimate result.

## 7. Cap the rounds

Audit-and-fix loops do not reach zero findings. Cap the rounds, watch the worst severity each round, and stop when it stops falling; then do one surgical fix pass. A "worthy, except for X" verdict is a fail.

## 8. Scripts have their own late failures

Build every prompt before the first dispatch so a typo fails in the first second. Workflow names are fixed when a session starts, so a freshly installed script may not be visible by name until you restart; call it by path. Do not resume a run after editing its script: start a fresh run.
