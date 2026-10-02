---
name: delegate
description: "Use when briefing a subagent: goal, owned files, done-check, return shape, and model every time."
model: inherit
category: dispatch-coordinate
---

# Delegate with a brief

A subagent starts with nothing but your brief. It does not see the session protocol, your conversation, or your earlier reading. Everything it needs goes in the prompt.

Template: `${CLAUDE_PLUGIN_ROOT}/skills/delegate/brief-template.md`.

## Should this be an agent at all?

- A fix under ten lines in one file: do it in the main thread. An agent costs more than it saves.
- Reading that answers one question: use `dojo-protocol:scout`.
- A change that spans files, with a check: use `dojo-protocol:builder`.
- Independent eyes on a result: `dojo-protocol:reviewer` or `dojo-protocol:judge`.

## The brief

1. **Goal**: one outcome, and why it matters.
2. **Owned files**: the paths this agent may write. Everything else is read-only by instruction, and "report a need" is the way out.
3. **Done-check**: the exact command and the result that counts. The agent runs it and shows the output.
4. **Facts you already hold**: `path:line` citations, decisions from the contract file. Do not make it rediscover them.
5. **Return shape**: what to send back (files changed, commands run with exit codes, open items), and its size. Big deliverables go to a file; reply with the path and a one-line summary.
6. **Rules it must carry**: subagents do not get the injected protocol. State the ones that apply: read before editing, verify before saying done, cite `path:line`, no git add/commit/push unless asked.

## Set `model` every time

Pass `model` on every Agent call and every workflow step: haiku to look things up, sonnet to build and review, opus to judge. Pinned plugin agents already carry a model. Everything else inherits the session's, which is usually the most expensive one.

## Run it so you can trust it

- Prefer foreground children. A background agent notifies the main session, not its parent, so a parent that waits for it can wait forever.
- Judge a background agent by what it wrote to disk, not by its stream or its own report. No writes after a long read means stalled: redirect it, narrow it, or take the work back.
- An agent that stalls twice gets built inline.
- Treat every report as a claim. Open the files, run the check, compare the changed files with the owned list.
- When you summarize a fan-out, give three numbers: dispatched, returned, failed. An agent that died looks like one that found nothing.

## A prompt is not a control

If a mistake would be costly (a stray write, a printed secret, a push), do not rely on a sentence in the brief. Choose the agent whose tools list cannot do it, or do that step yourself.

Related: rules 1, 4, 5 and 6 in `${CLAUDE_PLUGIN_ROOT}/PROTOCOL.md`; `contract` for the shared-decisions file.
