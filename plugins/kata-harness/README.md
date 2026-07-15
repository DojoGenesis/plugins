# kata-harness — Claude Code plugin

The Kata Roll adapter for Claude Code. Install it in a project that already
runs (or is starting) the [bring loop](../bring-loop/), then run the
`kata-harness-setup` skill once. From then on:

- **`kata-harness` skill**: say "start a roll" / "roll for 3 reps" / "do a
  25-minute roll" and the agent opens a bounded, self-terminating session over
  your existing `bring/` queue — surfacing ONE bring per tick, staging it
  (draft up, recipient confirmed, brief summarized), and stopping at the edge.
  You execute; it logs only on your word (`roll-resolve` / `roll-skip` /
  `roll-elapse`), then ticks the next rep until the target is reached. Rolling
  an unworked tick forward is not failure — the bring stays open.
- **SessionStart** injects the active roll's status — only while a session is
  actually open or paused, never as a second daily nag beside bring-loop's brief.
- **Opt-in timer** (`--timer`): count-up display, count-down when a cadence is
  set. A display, not a process — expiry never resolves or advances anything.

Contract, ledger schema, and conformance gate: [SPEC.md](SPEC.md). Core CLI
(works without Claude Code at all): [scripts/roll_core.py](scripts/roll_core.py).
Coexists with [bring-loop](../bring-loop/) by design — same queue
(`bring/actions.md`), same outcome ledger (`bring/ledger.jsonl`), its own
session ledger (`bring/roll-ledger.jsonl`). MIT attribution for the vendored
`bring_core.py` functions: [NOTICE](NOTICE).

---

*Distribution copy. Canonical source: [github.com/DojoGenesis/kata-harness](https://github.com/DojoGenesis/kata-harness) (`plugin/` dir + `SPEC.md`/`NOTICE`) - sync from there, do not edit here. Synced 2026-07-15 @ v0.1.1.*
