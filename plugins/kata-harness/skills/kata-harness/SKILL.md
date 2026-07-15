---
name: kata-harness
description: Run a bounded kata roll over the project's bring queue — start a session with an explicit target (reps or minutes), surface and stage exactly one bring per tick, log the outcome only on the human's word, then advance. Use when the user says "start a roll", "roll for N reps", "do a 25-minute roll", "tick", "next rep", "resolve this tick", "skip this tick", or "pause/resume/end the roll".
model: inherit
category: govern-publish
---

# Kata Harness — roll the bring queue, one tick at a time (never execute)

You are operating inside the kata-roll contract (repo spec: `SPEC.md` in the
kata-harness plugin/repo, extending bring-loop's `SPEC.md` by reference — its
five invariants bind, reinterpreted day -> tick, plus a sixth: **a roll is
bounded and self-terminating**). A roll ticks over the SAME `bring/` queue
bring-loop reads — it owns no separate queue, and a tick resolved here counts
identically toward bring's own week streams and streak (invariant #4). This
skill never edits `bring/actions.md` and never calls a verb beyond the ones
below — all state transitions happen in `roll_core.py`.

## Starting a roll

The user names a target — reps ("roll for 3 reps"), a duration ("do a
25-minute roll"), or both a duration and a per-rep cadence. A target is
**required**; a roll is bounded, never open-ended (invariant #6). If they
don't give one, ask for it before starting — do not default to unbounded.

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/roll_core.py" roll-start --reps 3
python "${CLAUDE_PLUGIN_ROOT}/scripts/roll_core.py" roll-start --minutes 25 --cadence 25m --timer
```

`--cadence` sets the default per-rep duration (`25m` count-down, or `open`
count-up); `--timer` opts the in-session count-up/down display on (off by
default — a roll is model-paced unless asked otherwise).

## Each tick

1. Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/roll_core.py" roll-tick`. This
   surfaces exactly ONE bring — never the remaining queue, never the deck as
   a to-do list. A short "on deck" preview (at most two) may ride along; it
   is context, not a second ask. If the output reports the target reached,
   the session is **completed** — say so plainly and stop; do not tick again.
2. **Stage it**: gather everything the human needs to execute in one motion —
   open/quote the draft, confirm the recipient and first line, summarize the
   decision brief, surface the relevant file or thread. Ask at most ONE
   clarifying question. If a timer is on, you may mention the count-up/down
   display — it is informational only, never a control event: expiry
   resolves nothing by itself.
3. **Stop at the edge.** You do not send, submit, decide, publish, or fire the
   outward act — not even with permission, not even mid-timer. If asked to
   fire it, decline once, kindly: the rep belongs to the human. Then stage
   harder so executing takes them seconds.

## Resolving a tick — only on their word

- **It happened:**
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/roll_core.py" roll-resolve --kind sent|decided|closed|shipped [--note "..."]`
- **A conscious decline:**
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/roll_core.py" roll-skip --note "<reason>"`
  A reason is required (invariant #3). Treat a logged skip as a success of
  the system, not a failure of the person.
- **Moving on without a decision** (the window passed, or they're not doing
  this one right now):
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/roll_core.py" roll-elapse`. This is
  **not** a skip — no reason needed, nothing is written to
  `bring/ledger.jsonl`, and the bring **stays open** for a future tick.
  Rolling forward is not failure; it is the mechanism — the roll remembers.

After any of the three, tick again for the next rep — repeat until the roll
reports `completed`.

## Holding or ending the session

- Stepping away without ending: `roll-pause`; later `roll-resume` re-carries
  the same target and cadence.
- Ending before the target is reached: `roll-abort` — terminal, and only ever
  at the human's request.
- A roll that reaches its target ends itself (`completed`); one that doesn't
  finish still isn't a failure — the bring stays open and the ledger
  remembers what happened.
- Anytime: `roll-status` reports where the session stands (tick N of target,
  cadence, the in-progress rep) and regenerates `bring/ROLL-STATUS.md`.

## Never

Never fire/send/submit/decide/publish the outward act, timer or no timer,
permission or no permission · never surface more than one rep as "the ask" ·
never treat an elapsed tick as a skip, or a skip as an elapse · never resolve
or skip without their word · never let a running clock resolve, skip, or
advance anything by itself — expiry is a display event, not a control one ·
never start a session without an explicit target · never write to
`bring/actions.md` (that file is bring-loop's; the roll only ticks over it).
