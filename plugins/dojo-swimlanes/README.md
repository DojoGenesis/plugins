# dojo-swimlanes

See a fan-out as a timeline: one lane per agent, a mark per tool call, refusals in red, live in a pane.

A fan-out is several agents working at once. `dojo-swimlanes` draws it as a timeline: one lane per agent, time left to right, a mark for each tool call, a red cross where a call was refused or failed.

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-swimlanes@dojo-genesis
```

## What is inside

| Component | Tier | What it does |
|---|---|---|
| `hooks/register.tsx` | mod (early access) | records each subagent's spawn, tool calls and end; the pane; the command |
| `hooks/model.ts` | mod | the rules, with no engine calls: waves, buckets, marks, the text strips |
| `types/index.d.ts` | mod | the state the drawings read |

This plugin is a mod only. It has no classic hooks, skills or agents; `commands/swimlanes.md` is the fallback that says how to turn the mod on.

## Mod: early access

Function hooks are off on many accounts. To try the mod:

```
export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1
```

(or add it under `env` in `~/.claude/settings.json`), then start a new session. The Claude desktop app runs mods without it.

## Commands

| Command | What it does |
|---|---|
| `/swimlanes` | opens the Swimlanes pane and answers one line, for example "3 agents in view" |
| `/swimlanes text` | answers the text form instead of opening a pane |
| `/swimlanes all` | toggles between the latest wave and every kept agent |

A wave is the set of agents spawned since the last moment no agent was running.

## What each surface draws

- **Desktop, VS Code and mobile:** a chart with a label column (number, label, model), a lane band from spawn to end, a mark per tool call coloured by kind (read, write, bash, agent, other) and as wide as the call lasted, a red cross for a refused or failed call, a dashed amber tail while an agent waits, an end glyph, a "now" line while agents are live, a time axis and a legend. Hover a mark for its tool, target, duration and the refusal text.
- **Terminal:** one row per agent with a strip of time buckets: a block where a call ran, a cross for a refused or failed call, a dot for idle, a dashed glyph for waiting.

## Settings

- `enabled` (default on): set it off in the plugin's settings to turn the mod off for every session.

## Kill switches

`DOJO_OFF=1`: the whole suite. `DOJO_SWIMLANES_OFF=1`: this plugin. Either one makes the mod a pass-through.

## Honest limits

- While agents run, the desktop chart is a plain image (an interactive frame reloaded each second and blinked), so hover tooltips appear once the wave settles.
- The terminal draws text strips, not a chart.
- It keeps the last 16 agents and 200 calls each.
- A ✗ marks a refused or a failed call; the chart does not tell the two apart except by the hover text.

## Tests

```
cd plugins/dojo-swimlanes && python3 -m unittest discover -s tests -v
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/dojo-swimlanes
```

Tested with Claude Code 2.1.295.
