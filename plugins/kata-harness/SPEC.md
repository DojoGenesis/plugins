# The Kata Roll — implementation spec v0.1 (Claude Code)

A bounded, self-terminating **roll** of surface-and-stage reps over the bring queue. Where the
[bring loop](../../../CoworkPluginsByDojoGenesis/plugins/bring-loop/SPEC.md) surfaces ONE outward
action per *day* at session start, a kata roll surfaces one bring **per tick** across a bounded
session — staging each to ready-to-fire, waiting while the human executes, logging the outcome (or a
conscious skip), and advancing — then bringing the next rep. The timer is the new primitive; the
**bring queue is the content**; every rep is still **surface + stage only**. This spec extends
bring-loop's `SPEC.md` by reference (its five invariants bind, reinterpreted day→tick) and is the
implementation artifact after `SCOUT.md` → the six Accepted `adr/000*.md` → **this**.

> **Scope (ratified 2026-07-13, [`RATIFIED.md`](./RATIFIED.md)):** v0.1 is **Claude Code only**.
> Hermes is a deferred future adapter (ADR-0003). No wall-clock daemon (ADR-0001). Files-only,
> surface + stage, free, Apache-2.0 (MIT on the vendored `bring_core.py` portions). Grounded in the
> source Roll model, `Kata/specs/kata-roll-interface-spec-v0.2.md` §1–2 — see [`DEFINITION.md`](./DEFINITION.md).

---

## 1. What it is (and the rep = Roll / session vocabulary)

A **kata roll** is a bounded, self-terminating practice/execution round borrowed from the BJJ sense
of a live "roll" — intentional, bounded, iterative, not graded, not final. A single goal (here, a
**bring**) is surfaced, optionally timed, worked by the human (**surface + stage only — never
auto-fired**), debriefed to persistent memory (here, the file **ledger**), and then either resolved
or **carried forward** ("rolling forward is not failure… the roll remembers", source §1).

**The one vocabulary inversion** (from [`DEFINITION.md`](./DEFINITION.md)) — the harness adds one
level above the source's atomic unit, and the word "roll" attaches to both:

| Level | Source (`DojoGenesis/kata` app) | This harness |
|---|---|---|
| Atomic unit | a **Roll** — one goal, one timed round, one debrief | a **tick / rep** — one surfaced **bring** (this IS the source's Roll) |
| Multi-unit | a day's `d20 × 3` allowance of Rolls | a bounded **roll session** — N reps or T minutes (invariant #6; a level the source does not name) |

So: **the per-tick rep is the source's Roll; the multi-rep run is the *session*.** Throughout this
spec, "rep" and "tick" are the atomic Roll; "session" (or "a roll") is the bounded run.

---

## 2. Invariants (what makes an implementation a Kata Roll)

Bring-loop's five, each reinterpreted one level down (day → tick), **plus a new #6** (ADR-0005,
Accepted). These are the conformance bar, not suggestions.

1. **ONE rep surfaced per tick** — never the remaining rep list. A tick may show the current rep
   plus, optionally, the same "deck of upcoming" preview `pick()` already uses (`DECK_SIZE = 2`) —
   never the whole session at once. Surfacing N reps *across* N ticks is the point; surfacing N reps
   *at once* is the list invariant #1 exists to kill, timer or no timer.
2. **Surface + stage only, at every tick — no exception for being inside a timed session.** The
   system pulls the draft/brief/recipient; **the human executes the outward act. No auto-send, no
   auto-fire, ever** — not even with permission, not even under a running timer. The rep is the point.
3. **A conscious skip is a valid, logged rep — per tick.** Logged with a reason. **New resolution
   the daily loop never needed:** an *elapsed, unresolved* tick is **not** a skip. The roll neither
   auto-skips nor force-closes it — it logs `tick_elapsed` (a non-outcome) and the underlying bring
   **stays open** in `bring/actions.md`. Elapsed-and-silent ≠ skipped-and-declined; conflating them
   reintroduces the silent-rot failure #3 exists to name. This is roll-forward: nothing lost, no shame.
4. **Streams stay separate — and ticks are not a sixth stream.** `sent / decided / closed / shipped
   / skipped` remain the only scored outcome streams. A session's own bookkeeping (ticks surfaced /
   resolved / skipped / elapsed) is *attendance metadata* in `roll-ledger.jsonl`, never blended into
   or reported as an outcome stream. "8 ticks this roll" and "3 sent this week" are different axes.
5. **One source per concern, two faces per surface — extended, not replaced.** The session's own
   concern (session shape) gets its own append-only source (`roll-ledger.jsonl`) and its own
   generated, parity-gated face (`ROLL-STATUS.md`), mirroring `actions.md` / `ledger.jsonl` /
   `SCOREBOARD.md` exactly (ADR-0004).
6. **NEW — a roll is bounded and self-terminating.** Every session declares an explicit target (a
   rep count **or** a duration) at `started`, and reaches exactly one terminal state: `completed`
   (target reached) or `aborted` (human ended it early). **There is no unbounded session.** An
   open-duration *count-up rep* is allowed *inside* a bounded session (source §1/§5.2 — a Roll's
   duration may be "open"); #6 forbids an unbounded *session*, never a count-up rep. Boundedness is
   what keeps a roll from drifting toward the "unattended process that just keeps going" pattern
   ADR-0001 draws a hard line against — and, being an invariant, the conformance gate can check it.

### Source-state → harness-event mapping (ADR-0004 grounding)

The source Roll's lifecycle `idle → active → paused → debriefed → (rolled_forward | abandoned)` maps
directly onto the per-tick events:

| Source Roll state | Harness event (rep-level) | Meaning |
|---|---|---|
| `idle` | (pre-surface) | selected but not yet ticked |
| `active` | `tick_surfaced` | this rep is surfaced + staged, awaiting the human |
| `paused` / (resume) | `paused` / `resumed` | session held / continued |
| `debriefed` | `tick_resolved` | human executed; outcome + note logged |
| `abandoned` (per rep) | `tick_skipped` | conscious, reasoned decline |
| `rolled_forward` | `tick_elapsed` | window passed unworked; **bring stays open** (roll-forward DNA) |
| (bounded run) `abandoned` (whole) | session `aborted` | human ended the session early |
| — (level the source doesn't name) | session `started` / `completed` | the bounded run's own boundaries |

---

## 3. `roll_core` interface

`scripts/roll_core.py` — a single stdlib-only script (no network, no telemetry), the harness's
equivalent of `bring_core.py` one layer up. Per ADR-0006 it **vendors** the specific `bring_core.py`
functions it needs rather than importing bring-loop as a live dependency (self-contained, easy to
review, MIT retained on the vendored portions). Per ADR-0004 its entire design is the same purity
discipline: **state is never a stored cursor — "which tick are we on" is always a fold over the
append-only ledger.**

### 3.1 The Rep (Roll) record

The in-memory record `roll_core` builds for the current rep, mapping the source `Roll` interface
(§2 of the source) onto harness terms. It is **computed**, never persisted as such (it is folded from
the ledgers on demand):

| Field | Source `Roll` field | Notes |
|---|---|---|
| `session_id` | (session-level; source has none) | stable slug, e.g. `2026-07-12-a` |
| `tick` | — | 1-indexed rep counter within the session |
| `bring_id` | `goal` | **the goal is a bring** — the `bring/actions.md` action id |
| `title` | `goal` (display) | resolved from `actions.md` |
| `kind` | — | the bring's stream: `send \| decide \| close \| ship` |
| `category` | `goal_category` | optional: `task \| project \| habit \| custom` (source `RollCategory`); harness metadata only |
| `duration_minutes` | `duration_minutes` | **optional**; count-down if set, count-up if absent/"open" |
| `elapsed_seconds` | `elapsed_seconds` | **computed** `= now − surfaced_at`; never stored/incremented (no daemon) |
| `state` | `state` | one of the mapped events in §2's table |
| `debrief` | `debrief` | the harness minimal analog: one outcome `note` line → `bring/ledger.jsonl` (not the app's 3-field + AI seed) |
| `rolled_forward_from` / `rolled_forward_to` | same | carry-forward linkage; in the harness the "stays-open bring" is the implicit forward, optional explicit linkage via note |
| `surfaced_at` / `resolved_at` | `started_at` / `completed_at` | UTC timestamps from the ledger events |

### 3.2 Vendored from `bring_core.py` (MIT retained, used unchanged)

`slugify`, `parse_actions`, `load_ledger`, `open_actions`, `pick`, `week_counts`, `streak`,
`scoreboard_text` — the queue-selection and outcome math. **These must not fork behavior:** a
roll-produced `sent` has to be indistinguishable to `week_counts`/`streak` from any other `sent`
(invariant #4). Pin the vendored copy to a known bring-loop version and record it in `NOTICE`
(see the drift note in §11).

### 3.3 New pure functions (Apache-2.0) — folds over the roll ledger

```python
# --- parsing / loading (mirrors load_ledger) ---
def parse_roll_events(text: str) -> list[dict]      # tolerant; never raises on content
def load_roll_ledger(path: str) -> list[dict]       # append-only event list

# --- the fold: "where are we" is always recomputed, never a cursor ---
def current_session(events: list[dict]) -> str | None
    # most recent `started` whose session has no later `completed`/`aborted`
def tick_index(events: list[dict], session_id: str) -> int
    # count of `tick_surfaced` since the latest `started`/`resumed` for this session
def in_progress_tick(events, session_id) -> int | None
    # latest `tick_surfaced` with NO matching tick_resolved/tick_skipped/tick_elapsed
def surfaced_ids(events, session_id) -> set[str]
    # bring_ids already surfaced this session (selection exclusion)
def session_target(events, session_id) -> dict      # {"reps": N} | {"minutes": T}
def session_cadence(events, session_id) -> str      # "25m" | "open" (default per-rep duration)
def target_reached(events, session_id, now) -> bool # reps done, or elapsed minutes ≥ target
def is_terminal(events, session_id) -> str | None   # "completed" | "aborted" | None

# --- rep selection: reuse the SHARED queue, minus this session's surfaced ids ---
def next_rep(actions, entries, events, session_id, today, now) -> dict | None
    # open_actions(...) → pick(...) minus surfaced_ids(...); builds the §3.1 Rep record

# --- the count-up timer: a PURE display, no process (ADR-0001) ---
def elapsed_seconds(now_ts, surfaced_at_ts) -> int
def timer_display(rep: dict, now_ts) -> str
    # count-UP by default (elapsed); count-DOWN (remaining = duration_minutes*60 − elapsed)
    # only when a duration is set on the rep/session — source rule verbatim

# --- generated face + parity gate (mirrors scoreboard_text / cmd_check) ---
def roll_status_text(actions, entries, events, today, now_ts) -> str
def roll_conformance(actions, entries, events) -> list[str]  # [] == conformant; see §8
```

### 3.4 Command verbs (flat subcommands, `bring_core.py` house style)

All accept `--root <dir>` (default cwd / `$BRING_ROOT`) and `--now YYYY-MM-DD`; the timer verbs also
accept `--now-ts <ISO8601>` for deterministic sub-day tests (default: real UTC now).

| Verb | Appends event(s) | Analog of | Notes |
|---|---|---|---|
| `roll-start` | `started` | (new) | **requires a target:** `--reps N` \| `--minutes T` (invariant #6); `--cadence 25m\|open` sets the default per-rep duration; `--timer` opts the count-up display on (off by default, ADR-0001); `--session-id` optional. Cadence/target live **only** in this `started` event — never in `actions.md` (ADR-0004). |
| `roll-tick` | `tick_surfaced` | `brief` | folds → selects the next bring (minus `surfaced_ids`) → prints exactly ONE staged rep (+ optional ≤2 deck). This is ADR-0001/0003's `next`/`advance`. If `target_reached`, it materializes `completed` (idempotent) instead of surfacing. |
| `roll-resolve` | `tick_resolved` (+ outcome to `bring/ledger.jsonl`) | `log <terminal>` | `--kind sent\|decided\|closed\|shipped [--note]`. **Dual-write, ordered** (§4.3): outcome to `bring/ledger.jsonl` FIRST (system of record), then `tick_resolved` cross-ref. Regenerates `ROLL-STATUS.md` (+ `SCOREBOARD.md`). = `debriefed`. |
| `roll-skip` | `tick_skipped` (+ `skipped` to `bring/ledger.jsonl`) | `log skipped` | `--note <reason>` **required** (invariant #3). = per-tick `abandoned`. |
| `roll-elapse` | `tick_elapsed` only | (new) | **No `bring/ledger.jsonl` write; the bring stays open.** Invoked when advancing past an unworked rep. **Never auto-fired by a daemon** — an explicit human/agent act (there is no daemon in v0.1 anyway). = `rolled_forward` DNA. |
| `roll-pause` / `roll-resume` | `paused` / `resumed` | (new) | `resumed` re-carries cadence/target. |
| `roll-abort` | `aborted` | (new) | human ends the session early. Session terminal. |
| `roll-status` | (regenerates `ROLL-STATUS.md`) | `scoreboard` | prints the current-roll face; materializes `completed` if `target_reached`. |
| `roll-check` | — | `check` | parity gate + conformance assertions (§8); exit 1 on drift/violation. |

`completed` is **detected by the fold** (`target_reached`) and **materialized once** by the next
`roll-tick`/`roll-status` invocation (idempotent — only if not already present). No process writes it
unattended; this keeps the core daemonless and file-driven.

---

## 4. File formats (the roll-ledger schema)

Layered on bring-loop's existing `bring/` files — **do not fork history** (ADR-0004). Four files:

| File | Owner | Concern |
|---|---|---|
| `bring/actions.md` | human + agent (unchanged) | intent — **untouched** by this harness (no roll config ever lives here) |
| `bring/ledger.jsonl` | tool, append-only (**+2 optional keys**) | outcome *content* — the only place an outcome's `kind`/`note` lives |
| `bring/roll-ledger.jsonl` | tool, append-only (**new**) | session *shape* — the continuity source of truth |
| `bring/ROLL-STATUS.md` | tool, generated (**new**) | human/agent current-roll face; **parity-gated** |

### 4.1 `bring/roll-ledger.jsonl` (new, append-only, tool-owned, never hand-edited)

One JSON object per lifecycle event:

```
{"utc":"...Z","session_id":"<slug>","event":"<event>","tick":<int>,"bring_id":"<id|null>","cadence":"<25m|open>","target":{"reps":N}|{"minutes":T},"duration_minutes":<int|null>}
```

Events (authoritative names — ADR-0004 + ADR-0005; the task's `session_started`/`session_completed`
map to `started`/`completed`):

| Event | Level | Carries | Meaning |
|---|---|---|---|
| `started` | session | `target`, `cadence`, `tick:0` | opens a bounded session (invariant #6) |
| `tick_surfaced` | rep | `tick`, `bring_id`, optional `duration_minutes` | a rep surfaced + staged (≈ `active`) |
| `paused` / `resumed` | session | (`resumed` re-carries `target`/`cadence`) | held / continued |
| `tick_resolved` | rep | `tick`, `bring_id` | rep closed to a terminal outcome; **cross-refs** the `bring/ledger.jsonl` line, does **not** duplicate its `kind`/`note` (≈ `debriefed`) |
| `tick_skipped` | rep | `tick`, `bring_id` | conscious per-tick skip (≈ `abandoned`) |
| `tick_elapsed` | rep | `tick`, `bring_id` | window passed unworked; **bring stays open** (≈ `rolled_forward`) |
| `completed` | session | (target reached) | session terminal — success |
| `aborted` | session | (human ended early) | session terminal |

- `session_id` — stable slug identifying one run (e.g. `2026-07-12-a`).
- `tick` — 1-indexed rep counter within that session.
- `bring_id` — the `actions.md` action id the tick surfaced. **The roll owns no separate queue** — it
  ticks over the same queue bring reads, reusing `pick()`'s due-soonest selection minus `surfaced_ids`.
- `cadence` / `target` / `duration_minutes` — carried only on `started` (and re-carried on `resumed`).
  **Nothing about roll config lives in `actions.md`** (it is tool session state, not human intent).

### 4.2 `bring/ledger.jsonl` — two new **optional** keys

When an outcome came from a roll, the existing `{"utc","date","kind","id","note"}` entry gains
`session_id` and `tick`. Verified against the real `bring_core.py`: `load_ledger` keeps any entry
whose `kind ∈ KINDS` (extra keys ride along untouched), and `week_counts`/`streak`/`scoreboard`
read only known keys — so **a roll-produced `sent` is arithmetically identical to any other `sent`**
(invariant #4). Exactly one system of record per concern: `bring/ledger.jsonl` owns the outcome's
*content*; `roll-ledger.jsonl` owns the session's *shape*.

### 4.3 The two-write ordering (crash-safety, ADR-0004)

`roll-resolve` writes two files in sequence. Order is fixed: **append the outcome to
`bring/ledger.jsonl` first** (it is the system of record for the outcome itself), **then** append
`tick_resolved` to `roll-ledger.jsonl`. If the second write is lost, the outcome still counts and the
cross-reference is recoverable on the next fold; the reverse ordering could credit a tick with no
outcome behind it. `roll-skip` follows the same order (`skipped` to `bring/ledger.jsonl`, then
`tick_skipped`). `roll-elapse` writes **only** `roll-ledger.jsonl` (no outcome exists).

### 4.4 `bring/ROLL-STATUS.md` — generated, parity-gated

Regenerated by folding `roll-ledger.jsonl` (cross-referencing `actions.md` for titles and
`bring/ledger.jsonl` for outcomes). Same role `SCOREBOARD.md` plays: current `session_id`, tick N of
target, cadence, started-at, the current rep's state (surfaced-awaiting-log / resolved / skipped /
elapsed), the count-up/down timer display for the in-progress rep **when `--timer` is on**, and recent
tick history. **Parity-gated** by `roll-check`: regenerate fresh, diff byte-for-byte against the file
on disk, exit 1 on drift — exactly how `cmd_check` gates `SCOREBOARD.md`.

### 4.5 The continuity rule (stated plainly)

"Which tick are we on" = fold `roll-ledger.jsonl` from the most recent `started`/`resumed` forward:
count `tick_surfaced` for the rep index; the in-progress rep is the latest `tick_surfaced` with no
matching `tick_resolved` / `tick_skipped` / `tick_elapsed`; if the latest event is `completed` /
`aborted`, the session is over. **No process — warm or cold — ever reads a cursor variable; every
process, every time, replays the ledger** and gets the identical answer.

> **The two "opens" — do not conflate.** `tick_elapsed` **closes the tick** (the fold advances the
> rep index; that tick is no longer in-progress) while **leaving the bring open** in `actions.md`
> (no terminal/skip entry, so `open_actions` still returns it for a future surfacing). Tick-state and
> bring-state are different axes. Within a session a surfaced bring is not re-surfaced (`surfaced_ids`
> excludes it); it returns to the general queue for the next session / daily bring.

---

## 5. The count-up timer (in-session, opt-in, per-rep — ADR-0001)

- **Opt-in, off by default.** Without `--timer`, a roll is model-paced / self-paced (the operator's
  own `/loop` or manual `roll-tick` cadence drives it). `--timer` turns on an elapsed display.
- **Count-up by default; count-down if a duration is set** — the source rule verbatim (§3/§5.2). The
  per-rep duration is the session `cadence` (`25m` → each rep counts down from 25:00; `open` → count
  up), overridable per-tick via `tick_surfaced.duration_minutes`.
- **A display, not a process.** It is `timer_display(rep, now)` = a pure function of the rep's
  `tick_surfaced` timestamp and "now". It holds **no state beyond the roll ledger**, starts no clock
  that outlives the session, spawns nothing, and **never fires an action**. It is categorically
  distinct from the deferred wall-clock daemon — there is **no daemon** in v0.1.
- Timer expiry (count-down hitting 0) **does not** resolve, skip, or advance anything — the rep stays
  in-progress until a human-driven `roll-resolve` / `roll-skip` / `roll-elapse`. Expiry is a display
  event, not a control event (invariant #2).

---

## 6. Claude Code adapter (v0.1 — the only shipped adapter)

A thin plugin under `plugin/` that translates Claude Code's surfaces into `roll_core.py` calls and
renders the result — **no roll logic is re-implemented in the adapter** (ADR-0003); all state
transitions happen in the shared core.

- **`skills/kata-harness/SKILL.md`** — the doctrine the agent operates under. Drives the lifecycle:
  `roll-start` (on "start a roll / roll for N reps / 25-minute roll") → `roll-tick` surfaces ONE rep →
  the agent **stages** it (draft up, recipient confirmed, brief summarized) and **stops at the edge**
  → on the human's word, `roll-resolve` / `roll-skip`; on advancing past an unworked rep, `roll-elapse`.
  **Never sends, submits, decides, or publishes — not even with permission** (invariant #2); if asked
  to fire, it declines once and stages harder. Surfaces exactly one rep as "the ask", never the deck
  as a to-do list.
- **`skills/kata-harness-setup/SKILL.md`** — mirrors `bring-setup`: runs `init` (reuse `bring_core init`
  if `bring/` is absent), explains the **two-surface split** (edition = doctrine via `ke`; runner =
  this plugin, installed adjacent), and makes the second install step unmissable (ADR-0002 risk).
- **`hooks/hooks.json` + `hooks/roll-status-injector.py`** — a **SessionStart** hook that injects the
  active roll's `ROLL-STATUS` summary **only when a session is live** (`roll-ledger.jsonl` has a
  non-terminal `started`) and only in projects that opted in (`bring/` exists). Fail-open: any error
  prints nothing, exits 0 (the exact contract as `bring-injector.py`).
  - **Coexistence with bring-loop:** this hook **reads and reports only — it never auto-starts or
    auto-ticks a roll.** Ticks are operator-invoked (via the skill, or `/loop` pointed at
    `roll-tick`). This keeps the roll from competing with bring-loop's own daily SessionStart brief
    and preserves invariants #1 and #2 (nothing advances unattended).
- **Cadence is host-supplied:** the operator's `/loop` (in-session) or self-pacing drives ticks;
  `roll_core.py` stays timer-agnostic. `ralph-loop`/`/ar:loop`/`ScheduleWakeup` are *possible*
  operator-chosen drivers, none mandated.

**The adapter surfaces + stages; it never fires the outward act.** That line binds every code path.

---

## 7. Packaging (ADR-0002 + ADR-0006)

Two surfaces, the split bring-loop already proved — **the prose edition ships free via `ke`; the
executable runner ships adjacent, never through `ke`'s promote pipeline.**

- **Prose edition (via `ke`).** A `kata-harness` skill (`SKILL.md`), a `roll-cadence` playbook, and any
  seeds — **every artifact `tier: prose`, `artifact_class ∈ {skill, playbook, seed}`, `allowed-tools`
  empty** (a non-empty `allowed-tools` forces a `capability` reclassification and breaks
  auto-promotion — `CONTRACT.md` tier-consistency rule). The edition *documents and references*
  `roll_core.py` as prose content; it is **not** declared a capability artifact.
- **Executable runner (adjacent).** The Claude Code plugin (hooks + skills + `roll_core.py`) ships via
  the **`DojoGenesis/plugins` marketplace** — the same native rail bring-loop's CC adapter uses, and
  the one artifact class NOT gated on the IP flip (methodology, already public).
- **Explicitly skipped for v0.1 (ratified):** routing the executable core through `sandbox-pending/` +
  ADR-013 **WASM capability review**. The core is stdlib-only / local-file-only / no-network, but it is
  code a runtime executes on a tick — precisely the shape the capability tier gates. Rather than
  contest that gate, keep bring-loop's line: the gate binds what `ke` *auto-installs*; what `ke` was
  never going to auto-install doesn't need to clear it.
- **Catalog:** add a fourth `kind: harness` row to `dojo-ke/public/catalog.json`, shaped identically
  to its three siblings — `status: "draft"`, `price_cents: 0`,
  `ke_command: "# coming soon — package via: ke publish"`. Stays **draft** (not live) until the runner
  is actually installable (plugin ships + `kata-harness-setup` exists), so a consumer never meets a
  listing they cannot complete.

---

## 8. Conformance gate (`roll-check`)

A `check`-style verb runnable against the Claude Code adapter's output (Hermes deferred — ADR-0003).
`roll_conformance(...)` returns `[]` when conformant, else a list of violations; `roll-check` also runs
the `ROLL-STATUS.md` parity diff. It verifies **at minimum**:

| # | Assertion | Invariant |
|---|---|---|
| a | Each `tick_surfaced` presents **exactly one** `bring_id`; the fold never emits the full remaining rep list at a tick | #1 |
| b | The core/adapter contains **no outward-action path** — import allow-list is stdlib minus `socket`/`urllib`/`http*`/`smtp*`/`asyncio` network; no `send`/`post`/`publish` of the bring itself | #2 |
| c | A `skip` logs identically regardless of which surface wrote it (same `bring/ledger.jsonl` shape + `tick_skipped`) | #3 |
| d | The session state round-trips: folding `roll-ledger.jsonl` twice (fresh process, no shared memory) yields the identical in-progress tick, target, and terminal status | #5 |
| e | `tick_elapsed` writes **nothing** to `bring/ledger.jsonl`; the bring remains in `open_actions` | #3 |
| f | Every terminated session has exactly one `completed`\|`aborted`; a `started` with a `reps:N` target never has an (N+1)th `tick_surfaced` before `completed` | #6 |
| g | `ROLL-STATUS.md` on disk equals a fresh regeneration (byte-for-byte parity) | #5 |

When the deferred Hermes adapter is built it must pass this **identical** gate before it ships — that
is the mechanism that keeps two runtimes in parity, not a one-time design-time check.

---

## 9. File manifest (what v0.1 creates)

New **standalone, PUBLIC** repo `github.com/DojoGenesis/kata-harness` (ADR-0006), sibling to `bring-loop`
— **not** folded into it, **not** homed in `dojo-editions`:

```
kata-harness/                              # new PUBLIC repo, Apache-2.0
├── SPEC.md                             # this document (extends bring-loop/SPEC.md by reference)
├── README.md                           # two-surface install: edition via ke + plugin adjacent
├── LICENSE                             # Apache-2.0 (kata-harness's own code + doctrine)
├── NOTICE                              # MIT attribution for vendored bring_core.py portions + pinned version
├── scripts/
│   └── roll_core.py                    # stdlib-only; vendored bring_core fns + new roll verbs (§3)
├── plugin/                             # Claude Code adapter — ships via DojoGenesis/plugins marketplace
│   ├── .claude-plugin/plugin.json      # name: kata-harness, version 0.1.0, license Apache-2.0
│   ├── hooks/
│   │   ├── hooks.json                  # SessionStart → roll-status-injector (report-only)
│   │   └── roll-status-injector.py     # inject ROLL-STATUS only when a roll is active; fail-open
│   └── skills/
│       ├── kata-harness/SKILL.md          # surface + stage + debrief doctrine; drives the lifecycle
│       └── kata-harness-setup/SKILL.md    # init + the two-surface split (mirrors bring-setup)
├── public/                            # the ke PROSE edition (ADR-0002) — doctrine only
│   ├── kata-harness/                      # tier: prose, allowed-tools empty; references roll_core.py as prose
│   │   ├── artifact.yaml
│   │   └── SKILL.md
│   ├── roll-cadence/                   # playbook (tier: prose)
│   │   ├── artifact.yaml
│   │   └── KNOWLEDGE.md
│   └── (seeds as needed, tier: prose)
└── tests/
    └── test_roll_core.py               # the §8 conformance gate + fold/timer unit tests
```

**Edit outside the new repo (not a new file):** one appended row in
`dojo-ke/public/catalog.json` (§7). *This spec does not make that edit — it is listed as build work.*

---

## 10. Binary success criteria (v0.1)

1. `roll-start --reps 3` then 3× (`roll-tick` → `roll-resolve`|`roll-skip`) folds to a `completed`
   session; `ROLL-STATUS.md` reads tick 3/3, completed.
2. `roll-tick` surfaces **exactly one** bring (+ optional ≤2 deck preview), never the full remaining
   list — asserted by conformance (a).
3. `roll_core.py` imports **no network module**; no code path sends/fires the bring — asserted by
   conformance (b). Adapters only surface + stage.
4. A roll-produced `sent` yields the **same** `week_counts`/`streak` as the identical `sent` without
   `session_id`/`tick` keys — asserted by test (invariant #4).
5. `roll-check` exits 0 when `ROLL-STATUS.md` matches the fold, exit 1 on drift — asserted by
   conformance (g).
6. **Cold reconstruction:** two independent `roll_core.py` invocations (no shared memory) over the
   same `roll-ledger.jsonl` compute the identical in-progress tick / target / terminal status —
   asserted by conformance (d).
7. `roll-elapse` writes only `tick_elapsed`; the bring stays in `open_actions`; nothing lands in
   `bring/ledger.jsonl` — asserted by conformance (e).
8. Every session reaches exactly one terminal state; a `reps:3` session refuses a 4th `tick_surfaced`
   before `completed` — asserted by conformance (f) (invariant #6).
9. `roll-tick` never re-surfaces a `bring_id` already surfaced this session — asserted by test
   (`surfaced_ids` exclusion).
10. The Claude Code adapter drives `start → tick → resolve` end-to-end with **no auto-fire** — the skill
    stages and stops; no adapter code path executes the outward act (invariant #2).

---

## 11. Out of scope for v0.1

Deferred by the ratified ADRs — **designed-for, not built now:**

- **Hermes bridge adapter** (ADR-0003) — v0.1 is Claude Code only; the `~/.hermes/config.yaml` hook/cron
  spike is a prerequisite of that deferred lane, not of v0.1.
- **External wall-clock daemon** — cron / launchd / `CronCreate` / `scheduled-tasks` firing reps
  (ADR-0001 Route C, a v0.2+ additive layer). When built it may only *surface* a rep and log the
  result — **never** be the process that performs the outward act.
- **WASM sandbox / capability-tier promotion** of the runner through `sandbox-pending/` + ADR-013
  (ADR-0002 — skipped; reopening it is a fresh decision, not scope creep).
- **MCP roll-server** (SCOUT Route E) — post-2026-07-15, discovery-server-filing-gated.
- **The Kata app's product surface** — the 3-field debrief (happened/stuck/energy), AI `next_seed`,
  the `d20 × 3` allowance, soft/hard paywall, RevenueCat/Supabase/Gateway-memory persistence. Those
  belong to the private Kata app; the harness reuses **none** of them (DEFINITION.md "IS NOT"). Its
  debrief is one outcome line to the file ledger; its memory is the ledger.
- **Linear `BringItCruz!` queue source** — files-only (`bring/actions.md`) is the commons default; a
  Linear-backed variant is a separate queue-source implementation (ADR-0004 open item).

## 12. Non-goals (the fence)

No accounts, no server, **no server-side install path**, no telemetry, no network, no auto-send /
auto-fire / daemon-that-acts, no blended score, no streak-shaming (red is reserved for *silent* rot,
never for rest or a bounded roll's open tail), **no selling** (`price_cents: 0`, Apache-2.0 / MIT on
vendored core).

> **Vendored-copy drift (flagged seam, ADR-0006 × ADR-0004).** `roll_core.py` *vendors* `bring_core.py`
> (does not import it) yet operates on the **same** `bring/actions.md` + `bring/ledger.jsonl` a live
> bring-loop install co-owns. Two copies of the queue/ledger logic over one set of files can diverge if
> bring-loop's core changes. **Mitigation:** pin the vendored version in `NOTICE`; the conformance gate's
> round-trip check (d) plus invariant #4's arithmetic-identity test catch divergence early. This is a
> real interaction to watch, not a blocker.
