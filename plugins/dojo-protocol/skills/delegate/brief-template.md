# Subagent brief (copy, fill in, send)

Model: <haiku | sonnet | opus>   (set `model` on the call)
Agent: <dojo-protocol:scout | dojo-protocol:builder | dojo-protocol:reviewer | dojo-protocol:judge | other>

## Goal

<One outcome. Why it matters. What is out of scope.>

## Files you own (write only these)

- `<path>`
- `<path>`

You may read anything. If the job needs a file that is not on this list, stop and report what you need and why. Do not edit it.

## Facts already established

- `<path:line>` - <what is there>
- Decision (from <contract file>): <one line>

## Done-check

Run this in this session and show the output and exit code:

`<command>`

Pass means: <exit 0 / these lines appear>. Do not pipe it through tail, head or grep.

## Rules you carry

- Read before you edit; keep context small (grep first, read excerpts).
- Done means the done-check ran and you showed its result.
- Cite `path:line` for facts about the code.
- No git add, commit or push unless this brief says so.
- If a fix fails twice for the same reason, stop and state the causal chain and the smallest experiment.

## Return

- Files changed
- Commands run, with exit codes
- Anything unfinished, and why
- Keep it under <N> lines. Anything bigger goes to `<path>`; reply with the path and one line.
