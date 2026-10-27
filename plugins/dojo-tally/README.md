# dojo-tally

Count returns, not dispatches: when a fan-out settles, the model hears what came back (returned, failed, silent, unchecked), and /tally refute sends a report to a judge.

A dead reviewer looks exactly like a clean one. `dojo-tally` reads what each agent of a fan-out did and
what it said, sorts the returns, and when the whole wave is done tells the model the count, so a quiet
failure is not read as a pass.

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-tally@dojo-genesis
```

## What is inside

| Component | Tier | What it does |
|---|---|---|
| `hooks/register.ts` | mod (early access) | waves, classification, the settle note, `/tally` and `/tally refute` |
| `types/index.d.ts` | mod | the ledger and the stored reports |

This plugin is a mod only. It has no classic hooks, skills or agents.

## Mod: early access

Function hooks are off on many accounts. To try the mod:

```
export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1
```

(or add it under `env` in `~/.claude/settings.json`), then start a new session.

What it does:

- **Waves.** The first spawn opens a wave; every agent spawned while it is open joins it. The wave settles
  when every member is done.
- **Done means done.** An agent that ends a turn but is still held by the engine (parked on background
  work of its own) is waiting, not returned. Nothing about it is reported until the engine says it is done,
  and then its last answer is the one judged.
- **Structured answers.** An agent run with an output schema (a workflow's `agent()` with `schema`) answers
  by calling StructuredOutput, so its last turn has no text. The arguments of its last accepted
  StructuredOutput call are its answer: judged like text, and what `/tally refute` hands the judge. A
  rejected try is not an answer, and the call itself is not counted as looking at anything.
- **Classification**, first match wins:
  - `failed`: an error, a refusal, an interrupt, an empty answer, or an agent the engine stopped;
  - `silent`: a clean verdict ("no defects found", "looks good") from an agent that looked at nothing;
  - `unchecked`: a claim of a passing check ("tests pass", "verified") from an agent that ran no shell
    command;
  - `returned`: everything else.
- **The settle note.** When a wave of `min_wave` or more agents settles, one toast, and one note added to
  the main conversation for the model to read: the counts and every agent that did not simply return.
- **Review.** `/tally refute <n>` sends that agent's report to the protocol's judge agent (or a general-purpose
  agent when the judge is not installed); the verdict is added to the conversation when it is done.

## Commands

| Command | What it does |
|---|---|
| `/tally` | the open wave and the last settled ones, one row per agent: outcome, work, how long it lived |
| `/tally refute <n>` | sends agent `n`'s report to a judge |
| `/refute <n>` | the same, as a shortcut, where no other plugin holds the name |

## Options

| Option | Default | Meaning |
|---|---|---|
| `min_wave` | `2` | the smallest wave that gets a settle note |
| `settle_note` | `true` | add the settle note to the conversation (the toast shows either way) |
| `judge_model` | `opus` | the model `/tally refute` asks for (`opus` or `sonnet`) |

## Kill switches

`DOJO_OFF=1`: the whole suite. `DOJO_TALLY_OFF=1`: this plugin. Either one makes the mod a pass-through.

## Honest limits

- `silent` and `unchecked` read the answer's wording: a verdict phrased in a way the patterns do not know is
  counted as returned.
- A shell command can check anything, so an agent that ran one and claims a pass is counted as returned
  even when the command checked something else.
- Only the last five waves are kept; `/tally refute` names agents by their number in the session.
- The bare `/refute` is only a shortcut: when another plugin holds the name (dojo-protocol's `refute` skill does, so the whole suite installed means no `/refute` from this plugin), Claude Code keeps it there. `/tally refute <n>` always works.
- Teammates (agents that idle between messages) are not tallied.
- A structured answer is kept in memory between the StructuredOutput call and the end of that agent's turn,
  so a hot reload in that window loses it and the agent is counted as an empty answer.
- A settle note arrives a few seconds after the last agent ends: the mod first asks the engine whether
  that agent is done.
- A `/tally refute` judge runs on the model you pick and costs what that model costs.

## Tests

```
cd plugins/dojo-tally && python3 -m unittest discover -s tests -v
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/dojo-tally
```

Tested with Claude Code 2.1.295.
