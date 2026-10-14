# dojo-lanes

Two agents writing one file clobber each other: the first writer holds the file while it runs, a second running agent is refused, and fan-outs get the shared contract.

The protocol's fourth rule says to give each agent files no one else writes. Until now that was a practice:
nothing stopped a second agent from editing a file the first was halfway through. `dojo-lanes` makes it a
lock between running subagents, and hands each subagent the fan-out's contract.

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-lanes@dojo-genesis
```

## What is inside

| Component | Tier | What it does |
|---|---|---|
| `hooks/register.ts` | mod (early access) | lane claims and refusals, the contract note, `/lanes` |
| `types/index.d.ts` | mod | the board the hooks share |

This plugin is a mod only. It has no classic hooks, skills or agents.

## Mod: early access

Function hooks are off on many accounts. To try the mod:

```
export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1
```

(or add it under `env` in `~/.claude/settings.json`), then start a new session.

What it does:

- **Lanes.** The first subagent to write a file (Edit, Write, NotebookEdit) holds it as its lane. While
  that agent runs, another subagent's write to the same file is refused, and the refusal tells it to put
  the change in its report instead. The main thread is never refused; a main-thread write into a held lane
  is logged once.
- **Release.** A lane is released when its agent is done. An agent that ends a turn but is still held by
  the engine (parked on background work of its own) keeps its lanes until the engine says it is done.
- **The contract note.** When a subagent is spawned and a contract file exists, or another writing agent
  is already running, a short note is added to its brief: where the shared decisions are, and that files
  it writes first become its lane.
- **Rule 4 nudge.** Two or more writing agents in flight with no contract file raise one toast per wave.

## Commands

| Command | What it does |
|---|---|
| `/lanes` | each agent, its state and the files it holds, then the contested writes |

## Options

| Option | Default | Meaning |
|---|---|---|
| `mode` | `lock` | `lock` refuses a second writer, `warn` lets it through and logs, `off` only records |
| `attach_contract` | `true` | add the contract note to subagent briefs |
| `contract_paths` | `CONTRACT.md,.dojo/CONTRACT.md,.dojo/dag-contract.md,.parallel-tracks/manifest.json` | where to look for the contract, first match wins |

## Kill switches

`DOJO_OFF=1`: the whole suite. `DOJO_LANES_OFF=1`: this plugin. Either one makes the mod a pass-through.

## Honest limits

- Paths are compared as written, after resolving relative paths and dots. Letter case and symbolic links
  are not resolved, so two spellings of one file on a case-insensitive disk are two lanes.
- Only the file tools are watched. A shell command that writes a file is not seen.
- A lane is held per file, not per region of a file.
- Agents a workflow script starts hold lanes like any other, but the engine does not list them, so their
  lanes are released only by their own turn end.
- The guard fails open: if it cannot decide, the write goes through.

## Tests

```
cd plugins/dojo-lanes && python3 -m unittest discover -s tests -v
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/dojo-lanes
```

Tested with Claude Code 2.1.295.
