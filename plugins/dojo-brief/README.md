# dojo-brief

Lints every subagent brief at dispatch against the delegate skill: detail, owned files, done-check, return shape. A notice, or one send-back.

A subagent sees nothing but its brief. The protocol's delegate skill lists what a brief carries; a thin one
is the usual cause of an agent that stalls or returns something no one can use. `dojo-brief` checks each
brief as it is dispatched.

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-brief@dojo-genesis
```

## What is inside

| Component | Tier | What it does |
|---|---|---|
| `hooks/register.ts` | mod (early access) | the lint at dispatch and `/dojo-brief` |

This plugin is a mod only. It has no classic hooks, skills or agents.

## Mod: early access

Function hooks are off on many accounts. To try the mod:

```
export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1
```

(or add it under `env` in `~/.claude/settings.json`), then start a new session.

What it checks, on every Agent call:

- **detail**: the brief is at least `min_chars` characters;
- **owned files**: it names a file or a directory, or says which files the agent may write;
- **done-check**: it says what done is and how to check it (not asked of read-only agent types);
- **return shape**: it says what to send back.

A fork inherits the whole conversation, so it is never linted. Model choice is left to `dojo-router`.

What happens to a brief that misses a field depends on `mode`:

- `notice`: the dispatch goes ahead and one dim line names what is missing;
- `sendback`: the first dispatch is refused once, with the list; a second dispatch with the same
  description goes through;
- `off`: nothing.

## Commands

| Command | What it does |
|---|---|
| `/dojo-brief` | puts the brief template in the prompt |
| `/dojo-brief stats` | how many briefs were linted this session and what they missed |

The command is `/dojo-brief`, not `/brief`: Claude Code has its own `/brief`.

## Options

| Option | Default | Meaning |
|---|---|---|
| `lint_briefs` | `true` | lint at dispatch; `false` turns the lint off and keeps the command |
| `mode` | `notice` | `notice`, `sendback` or `off` |
| `min_chars` | `200` | the shortest brief that is not thin |

## Kill switches

`DOJO_OFF=1`: the whole suite. `DOJO_BRIEF_OFF=1`: this plugin. Either one makes the mod a pass-through.

## Honest limits

- The checks read wording, on purpose loosely: a brief that mentions a test passes the done-check even
  when it does not say which one. They catch the missing field, not the weak one.
- A path with no extension and no backticks may not be recognised as a file.
- Goal, facts and the rules carried are prose; the lint does not judge them.
- The send-back is remembered per description for the session.

## Tests

```
cd plugins/dojo-brief && python3 -m unittest discover -s tests -v
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/dojo-brief
```

Tested with Claude Code 2.1.295.
