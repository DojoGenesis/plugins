# dojo-fleet

See every subagent of a fan-out live, steer one mid-flight, and catch stalls by their writes, not their word.

A fan-out is several agents working at once, and the main thread sees each one only when it reports back.
`dojo-fleet` shows them while they run: what each is doing, how long it has run, what it has written, and
which one has gone quiet. It lets you message one mid-flight, nudge a stalled one, or stop it.

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-fleet@dojo-genesis
```

## What is inside

| Component | Tier | What it does |
|---|---|---|
| `hooks/register.ts` | mod (early access) | tracks every subagent from its spawn, tool calls and turn ends; the stall check; the commands |
| `hooks/views.tsx` | mod | draws the Fleet pane, the band above the prompt and the agent bar |
| `hooks/model.ts` | mod | the rules, with no engine calls: stall reasons, writer detection, rows, chips, the nudge text |
| `types/index.d.ts` | mod | the state the drawings read |

This plugin is a mod only. It has no classic hooks, skills or agents.

## Mod: early access

Function hooks are off on many accounts. To try the mod:

```
export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1
```

(or add it under `env` in `~/.claude/settings.json`), then start a new session.

What it shows:

- **The band above the prompt**, while any agent is in play: one chip per agent (number, name, age, last
  tool or why it looks stalled, files written), then the counts, then **Open** and **Hide**. It wraps
  whatever else draws there instead of replacing it.
- **The Fleet pane** (`/fleet`, or **Open**): every agent of the session as a table, the most urgent first.
  It opens with the keyboard in it; Enter on a row shows that agent's brief, its last answer, a **Steer**
  field and **Nudge**, **Stop** and **Close**.
- **The agent bar**: with an agent's transcript open, the band shows that agent's row with **Nudge**,
  **Stop** and **Fleet**. The prompt below already messages that agent, so the bar does not repeat it.

How it judges an agent:

- **Waiting.** An agent can end a turn and still be alive, parked on background work of its own. A turn's
  end is checked against the engine's task list a moment later: an agent the engine still holds is shown
  as waiting, not done.
- **Stalled.** A running agent is flagged when it has made no tool call for `stall_minutes`, when a tool
  call has not returned in that time, or, for an agent whose brief asks it to write, when it has written
  nothing in that time. Progress is judged by what the agent does, never by what it says. An agent waiting
  on running agents of its own is not flagged.
- **Nudge** sends the agent one check-in. A writing agent is told to write a file it owns within its next
  few calls; any other agent is told to report what it has and what blocks it. If an agent stalls again
  after a nudge, the pane says to stop it and build that track inline.

## Commands

| Command | What it does |
|---|---|
| `/fleet` | opens the Fleet pane and answers with one line of counts |
| `/fleet list` | the table as text |
| `/fleet engine` | the engine's own task list, as the mod reconciles against it |
| `/steer <#n or name> <message>` | sends the message into that agent's loop |

All four run at once, even while a turn is in flight.

## Options

| Option | Default | Meaning |
|---|---|---|
| `stall_minutes` | `10` | minutes before an agent is flagged stalled; `0` turns stall checks off |
| `show_band` | `true` | draw the band above the prompt |
| `stall_toast` | `true` | one toast when an agent first looks stalled |

`DOJO_FLEET_STALL_MINUTES` overrides `stall_minutes` where settings cannot reach the plugin (headless runs,
tests).

## Kill switches

`DOJO_OFF=1`: the whole suite. `DOJO_FLEET_OFF=1`: this plugin. Either one makes the mod a pass-through: no
tracking, no band, no pane, no commands.

## Honest limits

- Writer detection reads the brief: a brief that asks to edit, write, implement or fix makes a writer; one
  that says to write nothing does not. An agent that writes anyway becomes a writer from its first write.
- Stall checks run every 15 seconds, so a flag can arrive up to that long after the threshold.
- An agent the mod never saw spawn (one started before the mod loaded) is listed under a short id until
  it is seen again.
- Agents a workflow script starts are tracked, but the engine does not list them, so they are never marked
  ended for being absent from that list.
- **Stop** goes through the normal permission check for the stop tool.
- The pane redraws on the same 15 second tick; ages between ticks are as of the last one.

## Tests

```
cd plugins/dojo-fleet && python3 -m unittest discover -s tests -v
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/dojo-fleet
```

Tested with Claude Code 2.1.295.
