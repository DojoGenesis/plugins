---
name: protocol
description: "Use when starting work or dispatching agents: which of the ten rules applies, and which model fits each role."
model: inherit
category: dispatch-coordinate
---

# Applying the Dojo Protocol

The ten rules are injected once at session start. The full text lives in one place: `${CLAUDE_PLUGIN_ROOT}/PROTOCOL.md`. Read it if it is not in your context. This skill does not repeat it; it tells you which rule to reach for and how. Rules are cited by number.

The injection reaches the main thread only. Subagents never see it, so a brief to a subagent has to carry the rules it needs (see the `delegate` skill). The four role agents in this plugin already carry theirs.

## Role to model

| Role | Agent | Model | Use it to |
|---|---|---|---|
| scout | `dojo-protocol:scout` | haiku | look things up: find, read a slice, cite `path:line` |
| builder | `dojo-protocol:builder` | sonnet | make a briefed change in files it owns and run the check |
| reviewer | `dojo-protocol:reviewer` | sonnet | read a change with fresh eyes, find real defects or say none |
| judge | `dojo-protocol:judge` | opus | try to refute claims and re-run the checks |

Plain subagent types and workflow steps have no pinned model. Pass `model` on every dispatch (rule 1). An omitted model inherits whatever the session runs on, which is usually your top tier.

## Tell, then action

| If you notice... | Do this | Rule |
|---|---|---|
| a subagent or workflow step about to start | set `model` and say why | 1 |
| an edit to code you have not read this session | search, read the slice, or send a scout | 2 |
| a large file, a log, a whole directory | grep, then read excerpts | 3 |
| a fix of a few lines in one file | do it yourself, no agent | 3 |
| three or more files, or two or more agents | write the shared decisions to a file first | 4 |
| you are about to write "done" or "tests pass" | run the check now and show it | 5 |
| a fan-out summary | give dispatched, returned and failed counts | 6 |
| you are about to patch | name the causal chain and the smallest experiment | 7 |
| it fails every time, at a boundary | check env, settings and credentials first | 8 |
| a probe came back empty | feed it a known positive before believing it | 9 |
| push, deploy, publish, delete, send | list what leaves the machine, ask, wait for yes | 10 |

## Which skill to open next

- Unread code to change: `scout-first`.
- Work that spans files or agents: `contract`, then `delegate` for each brief.
- A change or a claim to evaluate: `refute`.

## Overrides

- `./DOJO.md` in the project root replaces the injected text for that project.
- `DOJO_PROTOCOL_OFF=1` turns the injection off. `DOJO_OFF=1` turns off every Dojo plugin.

The protocol is injected text. Nothing enforces it; the agents' tools lists are the only hard limits in this plugin.
