---
description: "Run a parallel build: contract first, haiku scouts, sonnet builders, opus judges, and a scorecard that counts returns. Spends tokens on all three model tiers."
argument-hint: "<goal>"
allowed-tools: Read, Glob, Grep, Bash(python3:*)
---

Build this goal as parallel tracks: $ARGUMENTS

This command runs a workflow that calls a model for every track, on three tiers: haiku scouts, sonnet builders, opus for the contract, the advice and the audit. The cost grows with the number of tracks, and it is not capped for you. Say that to the person before you start, and do not run the workflow until they say yes.

## 1. Cut the goal into tracks (you, in this session)

Read enough of the repo to name the tracks yourself. Each track needs:

- `name`: short and unique.
- `prompt`: what a builder who has read nothing else must do.
- `files`: the explicit files or directories only that track will write. No globs. Repo-relative paths.

Cut by decisions as well as files. If one track settles something (a function name, a JSON shape, a file name) that another reads, they are not independent: merge them into one track. This workflow starts every track at the same time and does not order tracks, so it cannot run a dependent track after the one it needs. Use the `dojo-flow:dag-plan` skill if you need the method.

Also write down `gates`: the exact commands that must pass when the build is done (build, tests, lint). Without them the scorecard cannot say anything but UNVERIFIED.

## 2. Check the shape before any model runs

Run this with your tracks as the inline JSON (the build workflow ignores `deps`; add them here only to see how much of a plan is a chain):

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dag_ops.py" tracks --json '[{"name":"api","files":["src/api/"]},{"name":"ui","files":["src/ui/"]}]'
```

It exits 1 and says why if two tracks claim the same file, a path has a glob or `..` in it, or a name repeats. It reports the width: the number of tracks that can really run side by side. If the width is below the track count, say so and merge the coupled tracks into one. Do not hand the workflow tracks that depend on each other: it runs them all at once. If a later stage really needs an earlier one's output, run the earlier tracks as one build, let it finish, then start a separate build for the later tracks.

## 3. Confirm with the person

Show the tracks, their files, the gates, and the width. Say which paths the contract file will be written to (default `.dojo/dag-contract.md` in the repo; it is never overwritten if it exists, so on a re-run in the same repo pass a new `contractPath` such as `.dojo/dag-contract-2.md`, or remove the old file after reading it). Ask for a yes. If they would rather have the workflow propose the tracks, call it with no `tracks`: it stops after the contract phase and returns a plan, builds nothing, and you show that plan and ask again.

## 4. Run it

Call the Workflow tool (not the Skill tool; the command and the workflow share a name):

```
Workflow({
  name: "dojo-flow:build",
  args: { goal: "<goal>", tracks: [ {name, prompt, files: []} ], gates: ["<command>", "<command>"], repo: "<absolute repo path>" }
})
```

If the tool does not know that name (names are fixed when the session starts, so a plugin installed a minute ago is not visible yet), call it by path instead: `Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/build.js", args: { ... } })`.

Optional args: `models` ({scout, builder, integrator, reviewer, checker, judge} to haiku, sonnet or opus), `effort` (one level for every role, or a map by role), `adviceCap` (0 to 6, default 3), `maxTracks` (default 8, 16 at most), `contractPath`, `contractDraft`. Unknown keys and bad values are refused before anything runs.

## 5. Report it straight

Relay the scorecard text exactly as returned: the verdict, the dispatched, returned and failed counts, and every reason. Do not soften an UNVERIFIED into a summary.

If the verdict is VERIFIED, run at least one of the gate commands yourself in this session and show its result before you say it is done: the workflow's check results are reported by subagents, and the script has no shell of its own. If the verdict is anything else, list the reasons and what would clear each one.
