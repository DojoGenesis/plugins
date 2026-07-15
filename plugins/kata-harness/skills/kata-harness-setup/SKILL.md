---
name: kata-harness-setup
description: Set up the kata roll in a project that already runs (or is starting) the bring loop — confirm bring/ exists, explain where the roll's own ledger lives, walk through the opt-in timer, and make the two-plugin coexistence with bring-loop explicit. Use when the user says "set up kata-harness", "install the roll plugin", "add rolls on top of bring-loop", or asks how the timed roll relates to their daily bring.
model: inherit
category: govern-publish
---

# Kata-harness-setup — install the roll runner alongside bring-loop

A roll never runs on its own queue — it ticks over the **same** `bring/`
queue bring-loop already reads. Setup here is mostly about making sure that
foundation exists, then explaining the one new file and the one new plugin
surface layered on top of it.

## 1. Make sure the bring queue exists

Check for `bring/actions.md` in the project root.

- **Missing:** run `python "${CLAUDE_PLUGIN_ROOT}/scripts/bring_core.py" init`
  (kata-harness reuses bring-loop's own init rather than inventing a second
  queue format). It scaffolds `bring/actions.md` and `bring/ledger.jsonl`,
  never overwriting anything that already exists.
- **Present:** leave it alone. If bring-loop is already installed and in use,
  there is nothing to scaffold — the roll rides on the existing queue as-is.

If the queue is genuinely empty (a fresh init, or an existing one with
nothing in it), this is the moment to seed 2-3 real outward actions — ask the
user what they're sitting on, the same question bring-setup asks. A roll over
an empty queue has nothing to surface.

## 2. Where the roll's own ledger lives

Nothing to create by hand — the first `roll-start` call creates
`bring/roll-ledger.jsonl` on its own, the same way logging a bring creates
`bring/ledger.jsonl` on its own. Explain the shape of the file split, since
it's the one thing genuinely new here:

| File | Owner | Concern |
|---|---|---|
| `bring/actions.md` | human + agent (unchanged) | the queue — the roll never writes here |
| `bring/ledger.jsonl` | bring-loop, append-only | outcome content — `sent`/`decided`/`closed`/`shipped`/`skipped`, shared by both plugins |
| `bring/roll-ledger.jsonl` | kata-harness, append-only | session shape — ticks, targets, cadence, pauses; a bookkeeping axis of its own, never blended into the outcome streams |
| `bring/ROLL-STATUS.md` | kata-harness, generated | the current-roll face — regenerate with `roll-status`, never hand-edit |

## 3. The opt-in timer

**Model/self-paced by default** — no clock, no daemon, just tick when you're
ready.

- `--timer` on `roll-start` turns on an in-session display only: count-up if
  no duration is set, count-down if a cadence (e.g. `--cadence 25m`) is set.
- Say plainly that this is a **display, not a process** — it starts no clock
  that outlives the session, and expiry never resolves, skips, or advances a
  tick by itself. That stays true whether `--timer` is on or off.

## 4. Coexistence with bring-loop — say this explicitly

- **Distinct everything, on purpose:** plugin `kata-harness` (not `bring`),
  skills `kata-harness` / `kata-harness-setup` (not `bring` / `bring-setup`),
  ledger `bring/roll-ledger.jsonl` (not `ledger.jsonl`). Installing this
  plugin never touches bring-loop's own files, hooks, or skills.
- **Both keep running, unnagged by each other:** bring-loop's SessionStart
  brief and Stop nudge fire every session, same as always. This plugin's own
  SessionStart hook stays silent unless a roll is actually open right now —
  it is a status report, not a second daily nag.
- **One outcome ledger, shared honestly:** resolving a tick with
  `roll-resolve` writes to the *same* `bring/ledger.jsonl` bring-loop reads —
  a roll-produced `sent` counts toward the week's streams and the streak
  exactly like any other logged action. The roll adds a session on top; it
  does not fork the scoring.
- **One queue, never duplicated:** starting a roll does not copy or fork
  `bring/actions.md`. It ticks over the same open queue, minus whatever it
  has already surfaced this session.

## 5. Show them the shape

Walk through one real cycle so they see it end to end:
`roll-start --reps 3` (or `--minutes N`) -> `roll-tick` (one bring, staged)
-> their word -> `roll-resolve` / `roll-skip` / `roll-elapse` -> `roll-tick`
again -> ... -> `completed`. Two sentences of contract: the roll surfaces and
stages one rep per tick inside a bounded session; you execute, and rolling
forward an unworked tick is not a failure — the roll remembers.

## 6. Optional wiring (their call)

`roll-check` gates `ROLL-STATUS.md` freshness and a handful of conformance
assertions (see `SPEC.md`'s conformance gate section) — worth wiring into CI
only if they ask. Cadence itself is host-supplied: a manual `roll-tick` per
message, or their own `/loop` pointed at it — this plugin stays
timer-agnostic and never assumes a driver. Do not wire anything beyond this
project without being asked.
