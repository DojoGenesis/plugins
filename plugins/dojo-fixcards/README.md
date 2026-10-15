# dojo-fixcards

A tool call a Dojo guard refuses is drawn as a card: who blocked it, why, and the fix as code you can copy.

When a Dojo guard (dojo-gates, dojo-lanes, or a guard added later) refuses a tool call, the transcript shows a plain error. `dojo-fixcards` draws a card instead: the guard that blocked it, the reason, and the fix as code you can copy. Every other row is left to the engine.

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-fixcards@dojo-genesis
```

## What is inside

| Component | Tier | What it does |
|---|---|---|
| `hooks/register.tsx` | mod (early access) | reads a guard's refusal and draws the card; the command |
| `hooks/model.ts` | mod | the rules, with no engine calls: reading a guard's refusal text |
| `types/index.d.ts` | mod | the state the drawings read |

This plugin is a mod only. It has no classic hooks, skills or agents; `commands/fixcards.md` is the fallback that says how to turn the mod on.

## Mod: early access

Function hooks are off on many accounts. To try the mod:

```
export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1
```

(or add it under `env` in `~/.claude/settings.json`), then start a new session. The Claude desktop app runs mods without it.

## Commands

| Command | What it does |
|---|---|
| `/fixcards` or `/fixcards status` | on or off, and how many cards were drawn this session |
| `/fixcards off` | switches the cards off for this session |
| `/fixcards on` | switches them back on |

## What the card holds

Every surface gets the same card (a bordered box with text and code). For a dojo-lanes refusal the card names the file and the holder instead of a fix.

## Settings

- `enabled` (default on): set it off in the plugin's settings to turn the mod off for every session.

## Kill switches

`DOJO_OFF=1`: the whole suite. `DOJO_FIXCARDS_OFF=1`: this plugin. Either one makes the mod a pass-through.

## Honest limits

- In the terminal a folded tool group that holds a refusal is unfolded, and the raw refusal text still shows above the card (the engine ignored a rewrite of it).
- In the desktop app, tool calls sit inside a collapsed step row and the card is drawn with them, so it can only show once that row is expanded. The card has been seen in the terminal; on the desktop it is not yet confirmed.
- A subagent's refusal draws in that agent's own transcript.
- It reads dojo-gates and dojo-lanes refusal text; an unknown guard still gets a card with its reason.

## Tests

```
cd plugins/dojo-fixcards && python3 -m unittest discover -s tests -v
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/dojo-fixcards
```

Tested with Claude Code 2.1.295.
