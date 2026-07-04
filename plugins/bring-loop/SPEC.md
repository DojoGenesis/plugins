# The Bring Loop — pattern spec v0.1

A tiny protocol for gating **outward action** (sends, decisions, closes, ships)
in systems that already gate inward action (builds, tests, commits) — designed
to be navigable by humans and agents **equally**, from one source of truth.

## The problem (the BringItCruz effect)

Agentic tooling amplifies the build loop: gates, tests, CI, and agents make
*making* nearly frictionless. The outward loop — sending the invoice, making
the call, shipping the finished thing — stays ungated and unmeasured. The
result is a widening gap: finished work accumulating behind trivial outward
actions. Named for Cruz Romero Morales' operator persona **BringItCruz!**
("Built it, now bring it"), whose measured version of this gap was an 18.8-day
operator-queue item sitting beside a same-day agent queue.

## Invariants (what makes an implementation a Bring Loop)

1. **ONE action surfaced per day.** Never a list. Lists re-create the paralysis.
2. **Surface + stage only.** The system may pull up the draft, confirm the
   recipient, prepare the brief — the human executes the outward act. No
   auto-send, ever. The rep is the point.
3. **A conscious skip is a valid rep.** Logged with a reason. Declined beats
   expired; silent rot is the only failure state.
4. **Streams stay separate.** `sent / decided / closed / shipped / skipped`
   are counted independently — never blended into one gamified score.
5. **One source per concern, two faces per surface:**
   - `bring/actions.md` — intent. Humans and their agents write it; tools never do.
   - `bring/ledger.jsonl` — history. Tools append; nothing edits.
   - `bring/SCOREBOARD.md` — generated human face of history; a **parity gate**
     (`check`) fails when it drifts from source. (This is the dual-navigability
     pattern: agent face and human face generated from the same state, with a
     gate instead of good intentions.)

## File formats

### `bring/actions.md`
Optional YAML frontmatter: `weekly_send_cap` (int, default 5),
`weekends_free` (bool, default true). Then one `##` section per action:

```markdown
## Send the pilot invite to Jordan
kind: send            # send | decide | close | ship
due: 2026-07-07       # optional, YYYY-MM-DD
id: pilot-invite      # optional stable slug; defaults to slugified title
link: https://...     # optional
note: draft in email  # optional
```

An action leaves the queue when a **terminal** outcome (`sent/decided/closed/
shipped`) with its `id` exists in the ledger, or — for today only — when a
`skipped` entry with its `id` carries today's date. Pruning the text is the
human's business, on their schedule.

### `bring/ledger.jsonl`
Append-only, one JSON object per line:
`{"utc": "...Z", "date": "YYYY-MM-DD", "kind": "<stream>", "id": "...", "note": "..."}`

### Selection
Due-soonest first (undated last), then file order. Top 1 + a visible deck of 2.

### Scoring
Weeks are Mon–Sun. Streak = consecutive working days with ≥1 terminal entry,
counting back from today (an unlogged *today* doesn't break it; weekends walk
through when `weekends_free`).

## Reference implementation

`plugin/scripts/bring_core.py` — single file, Python stdlib, no network, no
telemetry. Commands: `init · brief [--json] · log · status · scoreboard ·
check`. `brief` is the integration point: anything that can print at session
start can host the loop (Claude Code hook, shell rc, editor task, MOTD).

## Adapters

- **Claude Code plugin** (`plugin/`): SessionStart hook injects the brief;
  Stop hook nudges once when today's bring went untouched; skills teach the
  agent the surface+stage contract.
- Anything else: call `brief` at your loop's start and `log` when the human
  says it happened. An adapter is conformant if it preserves the five
  invariants — especially #2.

## Non-goals

No accounts, no server, no telemetry, no auto-send integrations, no
motivational streak-shaming (red is reserved for *silent* rot, not for rest).
