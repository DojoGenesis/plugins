#!/usr/bin/env python3
"""roll_core.py — the Kata Harness roll, harness-agnostic core. Stdlib only, no network.

THE MECHANIC (extends bring-loop one level up — see SPEC.md): where the bring loop
surfaces ONE outward action per *day*, a kata **roll** surfaces one bring **per tick**
across a bounded, self-terminating session — staging each rep to ready-to-fire, waiting
while the human executes, logging the outcome (or a conscious skip/elapse), then advancing.
The timer is the new primitive; the bring queue is the content; every rep is still
**surface + stage only — the human executes the outward act, never this tool.**

THE CONTRACT (invariants; SPEC.md §2 — bring-loop's five, reinterpreted day -> tick, + a sixth):
  1. ONE rep surfaced per tick — never the remaining rep list (a <=2 "deck" preview may ride along).
  2. Surface + stage ONLY, every tick — no auto-send/auto-fire, ever, timer or no timer.
  3. A conscious skip is a valid, logged rep. An *elapsed* tick is NOT a skip: it logs
     nothing to bring/ledger.jsonl and the bring STAYS OPEN (roll-forward).
  4. Streams stay separate. A session's own bookkeeping (ticks surfaced/resolved/skipped/
     elapsed) is attendance metadata in roll-ledger.jsonl, never a scored outcome stream.
  5. One source per concern, two faces per surface: roll-ledger.jsonl (append-only session
     shape) + ROLL-STATUS.md (generated, parity-gated). State is ALWAYS a fold over the
     ledger — never a stored cursor. "Which tick are we on" = replay the ledger, every time.
  6. A roll is BOUNDED and self-terminating: every session declares a target (reps or
     minutes) at `started` and reaches exactly one terminal state (`completed`|`aborted`).

FILES (under <root>/bring/):
  actions.md          — the queue source. Human+agent face of intent. NEVER written here.
  ledger.jsonl        — outcomes, append-only. A roll outcome adds optional session_id/tick
                        keys; it is arithmetically identical to any other outcome (invariant #4).
  roll-ledger.jsonl   — session shape, append-only, tool-owned (new).
  SCOREBOARD.md       — generated bring face of history (regenerated on every outcome).
  ROLL-STATUS.md      — generated current-roll face (new). `roll-check` gates its freshness.

USAGE (all verbs accept --root <dir> and --now YYYY-MM-DD; timer verbs also --now-ts <ISO8601>):
  python roll_core.py roll-start --reps 3                      # or --minutes 25 --cadence 25m --timer
  python roll_core.py roll-tick                                # surface + stage exactly ONE bring
  python roll_core.py roll-resolve --kind sent --note "..."    # human executed -> log the outcome
  python roll_core.py roll-skip --note "<reason>"              # conscious decline (reason required)
  python roll_core.py roll-elapse                              # window passed; bring stays open
  python roll_core.py roll-pause | roll-resume | roll-abort
  python roll_core.py roll-status                              # regenerate + print the roll face
  python roll_core.py roll-check                               # conformance + parity gate (exit 1 on drift)
"""
from __future__ import annotations
import argparse
import datetime
import json
import os
import re
import sys

# Roll-ledger vocabulary (SPEC.md §4.1 — authoritative event names).
ROLL_EVENTS = ("started", "tick_surfaced", "paused", "resumed",
               "tick_resolved", "tick_skipped", "tick_elapsed",
               "completed", "aborted")
SESSION_TERMINAL = ("completed", "aborted")
TICK_CLOSERS = ("tick_resolved", "tick_skipped", "tick_elapsed")


# ===========================================================================
# --- vendored from bring_core.py (MIT) ---
# Copied unchanged (pin: bring-loop as of NOTICE). These MUST NOT fork behavior:
# a roll-produced `sent` has to be indistinguishable to week_counts/streak from
# any other `sent` (invariant #4). Do not edit — edit bring_core.py + re-vendor.
# ===========================================================================

KINDS = ("sent", "decided", "closed", "shipped", "skipped")
TERMINAL = ("sent", "decided", "closed", "shipped")
DEFAULT_SEND_CAP = 5
DECK_SIZE = 2


def slugify(title):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:60] or "action"


def parse_actions(text):
    """actions.md -> (config, [action dicts]). Never raises on content."""
    config = {"weekly_send_cap": DEFAULT_SEND_CAP, "weekends_free": True}
    lines = text.splitlines()
    i = 0
    if lines and lines[0].strip() == "---":          # optional frontmatter
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                for line in lines[1:j]:
                    m = re.match(r"^(\w+)\s*:\s*(.+)$", line.strip())
                    if not m:
                        continue
                    k, v = m.group(1), m.group(2).strip()
                    if k == "weekly_send_cap" and v.isdigit():
                        config["weekly_send_cap"] = int(v)
                    elif k == "weekends_free":
                        config["weekends_free"] = v.lower() not in ("false", "no", "0")
                i = j + 1
                break
    actions, cur = [], None
    for line in lines[i:]:
        h = re.match(r"^##\s+(.+?)\s*$", line)
        if h:
            cur = {"title": h.group(1), "kind": "send", "due": None,
                   "id": None, "link": "", "note": ""}
            actions.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"^(kind|due|id|link|note)\s*:\s*(.+?)\s*$", line)
        if m:
            cur[m.group(1)] = m.group(2)
    for a in actions:
        a["id"] = a["id"] or slugify(a["title"])
        if a["due"]:
            try:
                a["due_date"] = datetime.date.fromisoformat(a["due"][:10])
            except ValueError:
                a["due_date"] = None
        else:
            a["due_date"] = None
    return config, actions


def load_ledger(path):
    entries = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("kind") in KINDS:
                    entries.append(e)
    except OSError:
        pass
    return entries


def open_actions(actions, entries, today):
    """Queue = actions with no terminal outcome, minus same-day skips."""
    done_ids = {e.get("id") for e in entries if e.get("kind") in TERMINAL}
    skipped_today = {e.get("id") for e in entries
                     if e.get("kind") == "skipped" and e.get("date") == today.isoformat()}
    return [a for a in actions if a["id"] not in done_ids and a["id"] not in skipped_today]


def pick(actions_open):
    """Due-soonest first (undated last), then file order. Returns (top, deck)."""
    ranked = sorted(enumerate(actions_open),
                    key=lambda t: (t[1]["due_date"] or datetime.date.max, t[0]))
    ordered = [a for _, a in ranked]
    return (ordered[0] if ordered else None), ordered[1:1 + DECK_SIZE]


def week_counts(entries, today):
    monday = today - datetime.timedelta(days=today.weekday())
    counts = {k: 0 for k in KINDS}
    for e in entries:
        try:
            d = datetime.date.fromisoformat(e.get("date", ""))
        except (TypeError, ValueError):
            continue
        if monday <= d <= today and e.get("kind") in counts:
            counts[e["kind"]] += 1
    return counts


def streak(entries, today, weekends_free=True):
    days = {e.get("date") for e in entries if e.get("kind") in TERMINAL}
    n, d = 0, today
    if d.isoformat() in days:
        n += 1
    d -= datetime.timedelta(days=1)
    while True:
        if weekends_free and d.weekday() >= 5:
            d -= datetime.timedelta(days=1)
            continue
        if d.isoformat() in days:
            n += 1
            d -= datetime.timedelta(days=1)
        else:
            break
    return n


def scoreboard_text(config, actions, entries, today):
    counts = week_counts(entries, today)
    stk = streak(entries, today, config["weekends_free"])
    opn = open_actions(actions, entries, today)
    top, deck = pick(opn)
    lines = [
        "# Bring scoreboard",
        "",
        f"_Generated by bring_core.py for {today.isoformat()} — regenerate: "
        "`python bring_core.py scoreboard` · gate: `python bring_core.py check`_",
        "",
        f"**Streak:** {stk} working day(s)  ·  **This week:** "
        f"sent {counts['sent']}/{config['weekly_send_cap']} · decided {counts['decided']} · "
        f"closed {counts['closed']} · shipped {counts['shipped']} · skips {counts['skipped']}",
        "",
        "## Today",
        "",
    ]
    if top:
        due = f" (due {top['due']})" if top.get("due") else ""
        lines.append(f"- **{top['id']}** — {top['title']}{due}")
        for d in deck:
            lines.append(f"- on deck: {d['id']} — {d['title']}")
    else:
        lines.append("- queue clear")
    lines += ["", f"## Open queue ({len(opn)})", ""]
    for a in opn:
        due = f" (due {a['due']})" if a.get("due") else ""
        lines.append(f"- [{a['kind']}] {a['id']}{due}")
    lines += ["", "## Recent outcomes", ""]
    for e in entries[-10:][::-1]:
        note = f" — {e['note']}" if e.get("note") else ""
        lines.append(f"- {e.get('date', '?')} {e.get('kind', '?')} {e.get('id', '')}{note}")
    if len(entries) == 0:
        lines.append("- none yet")
    return "\n".join(lines) + "\n"


# ===========================================================================
# --- new pure functions (Apache-2.0) — folds over the roll ledger (SPEC §3.3) ---
# ===========================================================================

# --- parsing / loading (mirrors load_ledger) ------------------------------

def parse_roll_events(text):
    """roll-ledger text -> [event dicts]. Tolerant; never raises on content."""
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(e, dict) and e.get("event") in ROLL_EVENTS:
            events.append(e)
    return events


def load_roll_ledger(path):
    """Append-only event list from bring/roll-ledger.jsonl."""
    try:
        with open(path, encoding="utf-8") as f:
            return parse_roll_events(f.read())
    except OSError:
        return []


# --- the fold: "where are we" is always recomputed, never a cursor --------

def current_session(events):
    """Most recent `started` whose session has no later `completed`/`aborted`.

    Walk order == append order. `started` opens/adopts the active session;
    a terminal event for the active session clears it. paused/resumed keep it.
    """
    active = None
    for e in events:
        ev = e.get("event")
        if ev == "started":
            active = e.get("session_id")
        elif ev in SESSION_TERMINAL and e.get("session_id") == active:
            active = None
    return active


def tick_index(events, session_id):
    """Count of `tick_surfaced` in this session — the current/highest tick number.

    SPEC §3.3 phrases this "since the latest `started`/`resumed`"; §2 defines the
    tick as a "1-indexed rep counter within the SESSION". Those conflict once a
    pause/resume happens (there are never ticks *between* pause and resume, so a
    resume anchor would silently drop the pre-pause reps and restart numbering).
    We resolve in favor of §2: anchor at the session's single `started`, treating
    `resumed` as a NON-resetting anchor. This keeps tick numbers monotonic and
    UNIQUE within a session — which `in_progress_tick` below relies on to match a
    surfaced rep to its closer by tick number.
    """
    return sum(1 for e in events
               if e.get("session_id") == session_id and e.get("event") == "tick_surfaced")


def in_progress_tick(events, session_id):
    """Tick number of the latest `tick_surfaced` with NO matching closer, else None."""
    surfaced = [e for e in events
                if e.get("session_id") == session_id and e.get("event") == "tick_surfaced"]
    if not surfaced:
        return None
    tk = surfaced[-1].get("tick")
    closed = any(e.get("session_id") == session_id and e.get("event") in TICK_CLOSERS
                 and e.get("tick") == tk for e in events)
    return None if closed else tk


def surfaced_ids(events, session_id):
    """bring_ids already surfaced this session (selection exclusion)."""
    return {e.get("bring_id") for e in events
            if e.get("event") == "tick_surfaced" and e.get("session_id") == session_id
            and e.get("bring_id")}


def session_target(events, session_id):
    """{"reps": N} | {"minutes": T} — carried on `started`, re-carried on `resumed`."""
    target = {}
    for e in events:
        if e.get("session_id") == session_id and e.get("event") in ("started", "resumed"):
            t = e.get("target")
            if isinstance(t, dict):
                target = t
    return target


def session_cadence(events, session_id):
    """Default per-rep duration string: "25m" | "open" (default "open")."""
    cadence = "open"
    for e in events:
        if e.get("session_id") == session_id and e.get("event") in ("started", "resumed"):
            c = e.get("cadence")
            if c:
                cadence = c
    return cadence


def target_reached(events, session_id, now):
    """reps: closed-tick count >= N. minutes: elapsed since `started` >= T minutes."""
    target = session_target(events, session_id)
    if "reps" in target:
        return _closed_count(events, session_id) >= int(target["reps"])
    if "minutes" in target:
        start = _session_started_at(events, session_id)
        nowdt = _parse_iso(now)
        if start is None or nowdt is None:
            return False
        return (nowdt - start).total_seconds() >= int(target["minutes"]) * 60
    return False


def is_terminal(events, session_id):
    """"completed" | "aborted" | None — the session's terminal state, if any."""
    result = None
    for e in events:
        if e.get("session_id") == session_id and e.get("event") in SESSION_TERMINAL:
            result = e.get("event")
    return result


# --- rep selection: reuse the SHARED queue, minus this session's surfaced ids ---

def next_rep(actions, entries, events, session_id, today, now):
    """open_actions -> pick minus surfaced_ids -> the §3.1 Rep record (prospective).

    Returns the not-yet-surfaced rep (surfaced_at is None until the verb writes
    the tick_surfaced event), or None when the queue is exhausted for this session.
    """
    opn = open_actions(actions, entries, today)
    seen = surfaced_ids(events, session_id)
    remaining = [a for a in opn if a["id"] not in seen]
    top, deck = pick(remaining)
    if not top:
        return None
    cadence = session_cadence(events, session_id)
    return {
        "session_id": session_id,
        "tick": tick_index(events, session_id) + 1,
        "bring_id": top["id"],
        "title": top["title"],
        "kind": top["kind"],
        "category": top.get("category"),          # optional; harness metadata only
        "duration_minutes": _cadence_minutes(cadence),
        "elapsed_seconds": 0,                      # computed at display time, never stored
        "state": "tick_surfaced",
        "debrief": None,
        "rolled_forward_from": None,
        "rolled_forward_to": None,
        "due": top.get("due"),
        "surfaced_at": None,
        "resolved_at": None,
        "deck": [d["id"] for d in deck],
    }


# --- the count-up timer: a PURE display, no process (ADR-0001) -------------

def elapsed_seconds(now_ts, surfaced_at_ts):
    """now - surfaced_at, in whole seconds, floored at 0. Never stored/incremented."""
    now = _parse_iso(now_ts)
    start = _parse_iso(surfaced_at_ts)
    if now is None or start is None:
        return 0
    return max(0, int((now - start).total_seconds()))


def timer_display(rep, now_ts):
    """Count-UP by default (elapsed); count-DOWN (remaining) when a duration is set.

    A display, not a control event: expiry (remaining < 0) resolves nothing — the
    rep stays in-progress until a human-driven resolve/skip/elapse (SPEC §5).
    """
    elapsed = elapsed_seconds(now_ts, rep.get("surfaced_at"))
    dur = rep.get("duration_minutes")
    if dur:
        remaining = int(dur) * 60 - elapsed
        if remaining >= 0:
            return f"{_fmt_mmss(remaining)} left (of {int(dur):02d}:00)"
        return f"00:00 — {_fmt_mmss(-remaining)} over"
    return f"{_fmt_mmss(elapsed)} elapsed"


# --- generated face + parity gate (mirrors scoreboard_text / cmd_check) ----

def roll_status_text(actions, entries, events, today, now_ts=None):
    """Generate ROLL-STATUS.md. Content is a PURE function of (actions, entries,
    events, today) — deliberately NOT of now_ts, so the byte-for-byte parity gate
    (SPEC §8 g) is decidable. The second-ticking timer value would make parity
    impossible (now advances every second); instead this face records the stable
    timer ANCHOR (surfaced_at + duration/cadence), and the live count-up/down is
    rendered to stdout by the verbs (SPEC §5 — "a display, not a process").
    now_ts is accepted for interface fidelity with the §3.3 signature.
    """
    _ = now_ts  # intentionally unused for file content; see docstring
    L = ["# Kata roll status", ""]
    L.append(f"_Generated by roll_core.py for {today.isoformat()} — regenerate: "
             "`python roll_core.py roll-status` · gate: `python roll_core.py roll-check`_")
    L.append("")

    session = current_session(events)
    if session is None:                      # fall back to the most recent (terminal) session
        started = [e for e in events if e.get("event") == "started"]
        session = started[-1].get("session_id") if started else None
    if session is None:
        L.append("**No roll yet.** Start one: `python roll_core.py roll-start --reps N` "
                 "(or `--minutes T`).")
        L.append("")
        return "\n".join(L) + "\n"

    target = session_target(events, session)
    cadence = session_cadence(events, session)
    timer_on = _session_timer(events, session)
    term = is_terminal(events, session)
    started_ev = next((e for e in events if e.get("session_id") == session
                       and e.get("event") == "started"), None)
    started_at = started_ev.get("utc") if started_ev else "?"
    target_str = (f"{target['reps']} reps" if "reps" in target
                  else f"{target['minutes']} min" if "minutes" in target else "open")

    closed = _closed_count(events, session)
    idx = tick_index(events, session)
    ip = in_progress_tick(events, session)
    last = _last_session_event(events, session)
    paused = bool(last) and last.get("event") == "paused"

    L.append(f"**Session:** `{session}` · **target:** {target_str} · **cadence:** {cadence} · "
             f"**timer:** {'on' if timer_on else 'off'} · **started:** {started_at}")

    if term == "completed":
        denom = f"/{target['reps']}" if "reps" in target else ""
        state = f"completed — {closed}{denom} rep(s) done"
    elif term == "aborted":
        state = f"aborted — {closed} rep(s) done (through tick {idx})"
    elif paused:
        state = f"paused — tick {idx}, {closed} rep(s) done · `roll-resume` to continue"
    elif ip is not None:
        denom = f"/{target['reps']}" if "reps" in target else ""
        state = f"in progress — tick {ip}{denom} · surfaced bring awaiting log"
    elif "reps" in target and closed >= int(target["reps"]):
        state = (f"target reached — {closed}/{target['reps']} · run `roll-tick`/`roll-status` "
                 "to close the roll")
    else:
        state = f"awaiting next tick — {closed} rep(s) done, `roll-tick` to surface the next"
    L.append(f"**State:** {state}")
    L.append("")

    if ip is not None:
        rep = _inprogress_rep(actions, events, session)
        L.append("## Current rep")
        L.append("")
        if rep:
            due = f" (due {rep['due']})" if rep.get("due") else ""
            L.append(f"- **{rep['bring_id']}** — {rep['title']}  [{rep['kind']}]{due}")
            if timer_on:
                dur = rep.get("duration_minutes")
                if dur:
                    L.append(f"- timer: count-down from {int(dur):02d}:00 · "
                             f"surfaced {rep['surfaced_at']}")
                else:
                    L.append(f"- timer: count-up · surfaced {rep['surfaced_at']}")
            L.append("- contract: surface + stage only — the human executes, then "
                     "`roll-resolve --kind …` / `roll-skip --note …` / `roll-elapse`")
        L.append("")

    # tick history (cross-ref bring/ledger.jsonl for resolved/skipped outcomes)
    L.append("## Ticks this session")
    L.append("")
    outcome_by_tick = {e.get("tick"): e for e in entries
                       if e.get("session_id") == session and e.get("tick") is not None}
    any_tick = False
    for e in events:
        if e.get("session_id") != session:
            continue
        ev, tk = e.get("event"), e.get("tick")
        if ev == "tick_surfaced":
            any_tick = True
            L.append(f"- tick {tk}: surfaced `{e.get('bring_id')}`")
        elif ev == "tick_resolved":
            oc = outcome_by_tick.get(tk, {})
            note = f" — {oc.get('note')}" if oc.get("note") else ""
            L.append(f"- tick {tk}: resolved `{e.get('bring_id')}` → {oc.get('kind', '?')}{note}")
        elif ev == "tick_skipped":
            oc = outcome_by_tick.get(tk, {})
            note = f" — {oc.get('note')}" if oc.get("note") else ""
            L.append(f"- tick {tk}: skipped `{e.get('bring_id')}`{note}")
        elif ev == "tick_elapsed":
            L.append(f"- tick {tk}: elapsed `{e.get('bring_id')}` (stays open — roll-forward)")
    if not any_tick:
        L.append("- none yet")
    L.append("")

    # attendance metadata — explicitly NOT a scored outcome stream (invariant #4)
    L.append("## Attendance (session bookkeeping — not a scored outcome stream)")
    L.append("")
    L.append(f"surfaced {_count_ev(events, session, 'tick_surfaced')} · "
             f"resolved {_count_ev(events, session, 'tick_resolved')} · "
             f"skipped {_count_ev(events, session, 'tick_skipped')} · "
             f"elapsed {_count_ev(events, session, 'tick_elapsed')}")
    L.append("")
    return "\n".join(L) + "\n"


def roll_conformance(actions, entries, events):
    """[] == conformant; else a list of violation strings (SPEC §8 assertions a–f).

    Assertion (g) — ROLL-STATUS.md byte parity — needs the on-disk file and is run
    by cmd_roll_check, which appends its verdict to this list.
    """
    v = []

    # (a) each tick_surfaced presents EXACTLY ONE bring_id (a single id, never a list/null)
    for e in events:
        if e.get("event") == "tick_surfaced":
            bid = e.get("bring_id")
            if not isinstance(bid, str) or not bid:
                v.append(f"(a) tick_surfaced {e.get('session_id')}#{e.get('tick')} "
                         "does not present exactly one bring_id")

    # (b) no outward-action path: import allow-list is stdlib minus network modules
    for mod in _forbidden_imports():
        v.append(f"(b) forbidden network import present: {mod}")

    # (c) a skip logs identically regardless of surface: a `skipped` bring outcome exists
    for e in events:
        if e.get("event") == "tick_skipped":
            m = _match_outcome(entries, e.get("session_id"), e.get("tick"))
            if m is None or m.get("kind") != "skipped":
                v.append(f"(c) tick_skipped {e.get('session_id')}#{e.get('tick')} "
                         "has no matching `skipped` bring/ledger.jsonl outcome")

    # (d) the session state round-trips: fold a re-serialized ledger -> identical answers
    if not _round_trip_ok(events):
        v.append("(d) fold is not deterministic across re-serialization "
                 "(in-progress tick / target / terminal differ)")

    # (e) tick_elapsed writes NOTHING to bring/ledger.jsonl; the bring stays open
    done_ids = {x.get("id") for x in entries if x.get("kind") in TERMINAL}
    for e in events:
        if e.get("event") == "tick_elapsed":
            if _match_outcome(entries, e.get("session_id"), e.get("tick")) is not None:
                v.append(f"(e) tick_elapsed {e.get('session_id')}#{e.get('tick')} "
                         "has a bring/ledger.jsonl outcome (must have none)")
            if e.get("bring_id") in done_ids:
                v.append(f"(e) elapsed bring `{e.get('bring_id')}` is closed in "
                         "bring/ledger.jsonl (must stay open)")

    # (f) exactly one terminal per terminated session; reps:N never exceeds N tick_surfaced
    for sid in _session_ids(events):
        terms = [x for x in events
                 if x.get("session_id") == sid and x.get("event") in SESSION_TERMINAL]
        if len(terms) > 1:
            v.append(f"(f) session `{sid}` has {len(terms)} terminal events (must be exactly one)")
        target = session_target(events, sid)
        if "reps" in target:
            n_surf = _count_ev(events, sid, "tick_surfaced")
            if n_surf > int(target["reps"]):
                v.append(f"(f) session `{sid}` surfaced {n_surf} ticks > reps target "
                         f"{target['reps']} (an (N+1)th tick before completed)")
    return v


# ===========================================================================
# --- internal helpers (Apache-2.0) ----------------------------------------
# ===========================================================================

def _fmt_mmss(total_seconds):
    total_seconds = max(0, int(total_seconds))
    m, s = divmod(total_seconds, 60)
    return f"{m:02d}:{s:02d}"


def _cadence_minutes(cadence):
    """"25m" -> 25 (count-down); "open"/None/other -> None (count-up)."""
    if not cadence or cadence == "open":
        return None
    m = re.match(r"^(\d+)m$", cadence.strip())
    return int(m.group(1)) if m else None


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(dt):
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s):
    """Tolerant ISO8601 -> aware UTC datetime. Passes datetimes through; None on failure."""
    if s is None:
        return None
    if isinstance(s, datetime.datetime):
        return s if s.tzinfo else s.replace(tzinfo=datetime.timezone.utc)
    t = str(s).strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        dt = datetime.datetime.fromisoformat(t)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)


def _closed_count(events, session_id):
    return sum(1 for e in events
               if e.get("session_id") == session_id and e.get("event") in TICK_CLOSERS)


def _count_ev(events, session_id, ev_name):
    return sum(1 for e in events
               if e.get("session_id") == session_id and e.get("event") == ev_name)


def _last_session_event(events, session_id):
    last = None
    for e in events:
        if e.get("session_id") == session_id:
            last = e
    return last


def _session_started_at(events, session_id):
    for e in events:
        if e.get("session_id") == session_id and e.get("event") == "started":
            return _parse_iso(e.get("utc"))
    return None


def _session_timer(events, session_id):
    on = False
    for e in events:
        if e.get("session_id") == session_id and e.get("event") in ("started", "resumed"):
            if "timer" in e:
                on = bool(e.get("timer"))
    return on


def _session_ids(events):
    return [e.get("session_id") for e in events if e.get("event") == "started"]


def _action_by_id(actions, bring_id):
    for a in actions:
        if a["id"] == bring_id:
            return a
    return None


def _bring_of_tick(events, session_id, tick):
    for e in events:
        if (e.get("session_id") == session_id and e.get("event") == "tick_surfaced"
                and e.get("tick") == tick):
            return e.get("bring_id")
    return None


def _inprogress_rep(actions, events, session_id):
    """Reconstruct the in-progress rep from its tick_surfaced event (+ actions lookup)."""
    tk = in_progress_tick(events, session_id)
    if tk is None:
        return None
    ev = next((e for e in events if e.get("session_id") == session_id
               and e.get("event") == "tick_surfaced" and e.get("tick") == tk), None)
    if ev is None:
        return None
    a = _action_by_id(actions, ev.get("bring_id"))
    return {
        "session_id": session_id, "tick": tk, "bring_id": ev.get("bring_id"),
        "title": a["title"] if a else ev.get("bring_id"),
        "kind": a["kind"] if a else "?",
        "due": a.get("due") if a else None,
        "duration_minutes": ev.get("duration_minutes"),
        "surfaced_at": ev.get("utc"),
    }


def _match_outcome(entries, session_id, tick):
    for x in entries:
        if x.get("session_id") == session_id and x.get("tick") == tick:
            return x
    return None


def _forbidden_imports():
    """Scan THIS module's own source for network imports (SPEC §8 b import allow-list)."""
    deny = {"socket", "urllib", "http", "https", "smtplib", "ftplib", "asyncio",
            "requests", "telnetlib", "poplib", "imaplib", "xmlrpc", "ssl",
            "aiohttp", "httpx", "websocket", "websockets"}
    found = []
    try:
        with open(os.path.abspath(__file__), encoding="utf-8") as f:
            src = f.read()
    except OSError:
        return found
    for line in src.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        m = re.match(r"^(?:import|from)\s+([a-zA-Z0-9_.]+)", s)
        if m:
            mod = m.group(1).split(".")[0]
            if mod in deny:
                found.append(mod)
    return found


def _round_trip_ok(events):
    """Fold the live events and a re-serialized copy; every session must agree."""
    text = "\n".join(json.dumps(e, ensure_ascii=False) for e in events)
    reparsed = parse_roll_events(text)
    for sid in {e.get("session_id") for e in events if e.get("event") == "started"}:
        a = (in_progress_tick(events, sid), session_target(events, sid),
             is_terminal(events, sid), tick_index(events, sid))
        b = (in_progress_tick(reparsed, sid), session_target(reparsed, sid),
             is_terminal(reparsed, sid), tick_index(reparsed, sid))
        if a != b:
            return False
    return True


# ===========================================================================
# --- paths / io ------------------------------------------------------------
# ===========================================================================

def roll_paths(root):
    b = os.path.join(root, "bring")
    return {
        "dir": b,
        "actions": os.path.join(b, "actions.md"),
        "ledger": os.path.join(b, "ledger.jsonl"),
        "scoreboard": os.path.join(b, "SCOREBOARD.md"),
        "roll_ledger": os.path.join(b, "roll-ledger.jsonl"),
        "roll_status": os.path.join(b, "ROLL-STATUS.md"),
    }


def load_roll_all(root):
    """(config, actions, bring_entries, roll_events) — the full fold input."""
    p = roll_paths(root)
    try:
        with open(p["actions"], encoding="utf-8") as f:
            config, actions = parse_actions(f.read())
    except OSError:
        config, actions = {"weekly_send_cap": DEFAULT_SEND_CAP, "weekends_free": True}, []
    return config, actions, load_ledger(p["ledger"]), load_roll_ledger(p["roll_ledger"])


def _append_roll_event(root, event):
    p = roll_paths(root)
    os.makedirs(p["dir"], exist_ok=True)
    with open(p["roll_ledger"], "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _append_bring_outcome(root, entry):
    """Append-only to bring/ledger.jsonl — never rewrites it (co-writes safely with a
    live bring-loop; the shared ledger is append-only for both tools)."""
    p = roll_paths(root)
    os.makedirs(p["dir"], exist_ok=True)
    with open(p["ledger"], "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _write_scoreboard(root, config, actions, entries, today):
    """Regenerate bring/SCOREBOARD.md via the vendored, byte-identical generator."""
    p = roll_paths(root)
    os.makedirs(p["dir"], exist_ok=True)
    with open(p["scoreboard"], "w", encoding="utf-8") as f:
        f.write(scoreboard_text(config, actions, entries, today))


def _write_roll_status(root, actions, entries, events, today, now_ts):
    p = roll_paths(root)
    os.makedirs(p["dir"], exist_ok=True)
    with open(p["roll_status"], "w", encoding="utf-8") as f:
        f.write(roll_status_text(actions, entries, events, today, now_ts))


def _new_session_id(events, today):
    base = today.isoformat()
    existing = {e.get("session_id") for e in events if e.get("event") == "started"}
    for c in "abcdefghijklmnopqrstuvwxyz":
        sid = f"{base}-{c}"
        if sid not in existing:
            return sid
    return f"{base}-{len(existing) + 1}"


def _materialize_completed(root, session_id, events, now_ts):
    """Append `completed` once (idempotent). Caller has already checked target_reached."""
    if is_terminal(events, session_id):
        return events
    ev = {"utc": _iso(now_ts), "session_id": session_id, "event": "completed",
          "tick": 0, "bring_id": None}
    _append_roll_event(root, ev)
    return events + [ev]


def _print_rep(rep, events, session_id, now_ts, deck=None):
    """Print the ONE staged rep (+ optional <=2 deck + live timer) to stdout."""
    if not rep:
        return
    due = f" (due {rep['due']})" if rep.get("due") else ""
    print(f"  → [{rep.get('kind', '?')}] {rep['bring_id']} — {rep.get('title', rep['bring_id'])}{due}")
    if _session_timer(events, session_id):
        print(f"     timer: {timer_display(rep, now_ts)}")
    if deck:
        print("     on deck (context, not a to-do): " + ", ".join(deck))
    print("     surface + stage only — the human executes. Then: "
          "roll-resolve --kind <sent|decided|closed|shipped> [--note] · "
          "roll-skip --note <reason> · roll-elapse")


# ===========================================================================
# --- command verbs (flat subcommands, bring_core.py house style) ----------
# Mutating verbs append ONE roll event (resolve/skip append the bring outcome
# FIRST, per §4.3), THEN regenerate ROLL-STATUS.md — in that fixed order.
# ===========================================================================

def cmd_roll_start(root, a, today, now_ts):
    config, actions, entries, events = load_roll_all(root)
    active = current_session(events)
    if active:
        print(f"roll-start: a roll is already active (`{active}`). "
              "Finish it (`roll-abort`) before starting another (invariant #6: one bounded run).")
        return 1
    sid = a.session_id or _new_session_id(events, today)
    target = {"reps": a.reps} if a.reps is not None else {"minutes": a.minutes}
    cadence = a.cadence or "open"
    ev = {"utc": _iso(now_ts), "session_id": sid, "event": "started", "tick": 0,
          "bring_id": None, "cadence": cadence, "target": target,
          "duration_minutes": _cadence_minutes(cadence), "timer": bool(a.timer)}
    _append_roll_event(root, ev)
    events = events + [ev]
    _write_roll_status(root, actions, entries, events, today, now_ts)
    tgt = f"{a.reps} reps" if a.reps is not None else f"{a.minutes} min"
    print(f"roll-start: session `{sid}` — target {tgt}, cadence {cadence}, "
          f"timer {'on' if a.timer else 'off'}. Next: `roll-tick` to surface rep 1.")
    return 0


def cmd_roll_tick(root, a, today, now_ts):
    config, actions, entries, events = load_roll_all(root)
    session = current_session(events)
    if session is None:
        print("roll-tick: no active roll. Start one: `roll-start --reps N` (or `--minutes T`).")
        return 1
    last = _last_session_event(events, session)
    if last and last.get("event") == "paused":
        print(f"roll-tick: roll `{session}` is paused. Run `roll-resume` first.")
        return 1
    term = is_terminal(events, session)
    if term:
        print(f"roll-tick: roll `{session}` is {term}. Start a new roll to continue.")
        return 0
    # An in-progress rep must be closed before advancing — expiry never force-closes it (§5).
    ip = in_progress_tick(events, session)
    if ip is not None:
        rep = _inprogress_rep(actions, events, session)
        print(f"roll-tick: rep {ip} is still in progress — resolve/skip/elapse before advancing.")
        _print_rep(rep, events, session, now_ts)
        return 0
    # No rep open: if the target is reached, materialize `completed` instead of surfacing.
    if target_reached(events, session, now_ts):
        events = _materialize_completed(root, session, events, now_ts)
        _write_roll_status(root, actions, entries, events, today, now_ts)
        print(f"roll-tick: target reached — roll `{session}` completed "
              f"({_closed_count(events, session)} rep(s)). Nothing more to surface.")
        return 0
    # Surface exactly ONE next bring (minus this session's surfaced ids).
    rep = next_rep(actions, entries, events, session, today, now_ts)
    if rep is None:
        print(f"roll-tick: queue clear — no un-surfaced brings left this session. "
              "Add to bring/actions.md, or `roll-abort` to end early.")
        return 0
    ev = {"utc": _iso(now_ts), "session_id": session, "event": "tick_surfaced",
          "tick": rep["tick"], "bring_id": rep["bring_id"],
          "cadence": session_cadence(events, session),
          "target": session_target(events, session),
          "duration_minutes": rep["duration_minutes"]}
    _append_roll_event(root, ev)
    events = events + [ev]
    rep["surfaced_at"] = ev["utc"]
    _write_roll_status(root, actions, entries, events, today, now_ts)
    N = session_target(events, session).get("reps")
    head = f"rep {rep['tick']}" + (f"/{N}" if N else "")
    print(f"roll-tick: {head} surfaced.")
    _print_rep(rep, events, session, now_ts, deck=rep.get("deck", []))
    return 0


def cmd_roll_resolve(root, a, today, now_ts):
    config, actions, entries, events = load_roll_all(root)
    session = current_session(events)
    if session is None:
        print("roll-resolve: no active roll.")
        return 1
    ip = in_progress_tick(events, session)
    if ip is None:
        print("roll-resolve: no in-progress rep. Run `roll-tick` first.")
        return 1
    bring_id = _bring_of_tick(events, session, ip)
    # §4.3 two-write ordering: the OUTCOME (system of record) lands FIRST ...
    outcome = {"utc": _iso(now_ts), "date": today.isoformat(), "kind": a.kind,
               "id": bring_id or "", "note": a.note or "",
               "session_id": session, "tick": ip}
    _append_bring_outcome(root, outcome)
    entries = entries + [outcome]
    # ... THEN the roll-ledger cross-ref (recoverable on the next fold if this write is lost).
    rev = {"utc": _iso(now_ts), "session_id": session, "event": "tick_resolved",
           "tick": ip, "bring_id": bring_id}
    _append_roll_event(root, rev)
    events = events + [rev]
    _write_scoreboard(root, config, actions, entries, today)   # keep bring's face fresh
    _write_roll_status(root, actions, entries, events, today, now_ts)
    print(f"roll-resolve: tick {ip} → {a.kind} `{bring_id}` "
          "(logged to bring/ledger.jsonl + roll cross-ref).")
    if target_reached(events, session, now_ts):
        print("  target reached — run `roll-tick` or `roll-status` to close the roll.")
    return 0


def cmd_roll_skip(root, a, today, now_ts):
    config, actions, entries, events = load_roll_all(root)
    session = current_session(events)
    if session is None:
        print("roll-skip: no active roll.")
        return 1
    ip = in_progress_tick(events, session)
    if ip is None:
        print("roll-skip: no in-progress rep. Run `roll-tick` first.")
        return 1
    bring_id = _bring_of_tick(events, session, ip)
    outcome = {"utc": _iso(now_ts), "date": today.isoformat(), "kind": "skipped",
               "id": bring_id or "", "note": a.note, "session_id": session, "tick": ip}
    _append_bring_outcome(root, outcome)                       # same order as resolve (§4.3)
    entries = entries + [outcome]
    sev = {"utc": _iso(now_ts), "session_id": session, "event": "tick_skipped",
           "tick": ip, "bring_id": bring_id}
    _append_roll_event(root, sev)
    events = events + [sev]
    _write_scoreboard(root, config, actions, entries, today)
    _write_roll_status(root, actions, entries, events, today, now_ts)
    print(f"roll-skip: tick {ip} skipped `{bring_id}` — {a.note}. A logged skip is a valid rep.")
    if target_reached(events, session, now_ts):
        print("  target reached — run `roll-tick` or `roll-status` to close the roll.")
    return 0


def cmd_roll_elapse(root, a, today, now_ts):
    config, actions, entries, events = load_roll_all(root)
    session = current_session(events)
    if session is None:
        print("roll-elapse: no active roll.")
        return 1
    ip = in_progress_tick(events, session)
    if ip is None:
        print("roll-elapse: no in-progress rep to elapse. Run `roll-tick` first.")
        return 1
    bring_id = _bring_of_tick(events, session, ip)
    # No bring/ledger.jsonl write — the bring stays OPEN (roll-forward, invariant #3).
    eev = {"utc": _iso(now_ts), "session_id": session, "event": "tick_elapsed",
           "tick": ip, "bring_id": bring_id}
    _append_roll_event(root, eev)
    events = events + [eev]
    _write_roll_status(root, actions, entries, events, today, now_ts)
    print(f"roll-elapse: tick {ip} elapsed `{bring_id}` — window passed, bring stays open "
          "(roll-forward; nothing lost, no skip).")
    if target_reached(events, session, now_ts):
        print("  target reached — run `roll-tick` or `roll-status` to close the roll.")
    return 0


def cmd_roll_pause(root, a, today, now_ts):
    config, actions, entries, events = load_roll_all(root)
    session = current_session(events)
    if session is None:
        print("roll-pause: no active roll.")
        return 1
    last = _last_session_event(events, session)
    if last and last.get("event") == "paused":
        print(f"roll-pause: roll `{session}` is already paused.")
        return 0
    ev = {"utc": _iso(now_ts), "session_id": session, "event": "paused",
          "tick": 0, "bring_id": None}
    _append_roll_event(root, ev)
    events = events + [ev]
    _write_roll_status(root, actions, entries, events, today, now_ts)
    print(f"roll-pause: roll `{session}` paused. Resume with `roll-resume`.")
    return 0


def cmd_roll_resume(root, a, today, now_ts):
    config, actions, entries, events = load_roll_all(root)
    session = current_session(events)
    if session is None:
        print("roll-resume: no active roll.")
        return 1
    last = _last_session_event(events, session)
    if not last or last.get("event") != "paused":
        print(f"roll-resume: roll `{session}` is not paused.")
        return 0
    ev = {"utc": _iso(now_ts), "session_id": session, "event": "resumed", "tick": 0,
          "bring_id": None, "cadence": session_cadence(events, session),
          "target": session_target(events, session), "timer": _session_timer(events, session)}
    _append_roll_event(root, ev)
    events = events + [ev]
    _write_roll_status(root, actions, entries, events, today, now_ts)
    print(f"roll-resume: roll `{session}` resumed (target + cadence re-carried).")
    return 0


def cmd_roll_abort(root, a, today, now_ts):
    config, actions, entries, events = load_roll_all(root)
    session = current_session(events)
    if session is None:
        print("roll-abort: no active roll.")
        return 1
    ev = {"utc": _iso(now_ts), "session_id": session, "event": "aborted",
          "tick": 0, "bring_id": None}
    _append_roll_event(root, ev)
    events = events + [ev]
    _write_roll_status(root, actions, entries, events, today, now_ts)
    print(f"roll-abort: roll `{session}` aborted ({_closed_count(events, session)} rep(s) done). "
          "Un-worked brings remain open in bring/actions.md.")
    return 0


def cmd_roll_status(root, a, today, now_ts):
    config, actions, entries, events = load_roll_all(root)
    session = current_session(events)
    # Materialize `completed` iff the target is reached AND no rep is mid-flight (§3.4).
    if (session and not is_terminal(events, session)
            and in_progress_tick(events, session) is None
            and target_reached(events, session, now_ts)):
        events = _materialize_completed(root, session, events, now_ts)
    _write_roll_status(root, actions, entries, events, today, now_ts)
    p = roll_paths(root)
    try:
        with open(p["roll_status"], encoding="utf-8") as f:
            sys.stdout.write(f.read())
    except OSError:
        pass
    # Live timer to stdout only (kept out of the parity-checked file, §5/§8 g).
    if session:
        ip = in_progress_tick(events, session)
        if ip is not None and _session_timer(events, session):
            rep = _inprogress_rep(actions, events, session)
            print(f"timer: {timer_display(rep, now_ts)}")
    return 0


def cmd_roll_check(root, a, today, now_ts):
    config, actions, entries, events = load_roll_all(root)
    p = roll_paths(root)
    violations = roll_conformance(actions, entries, events)
    # (g) ROLL-STATUS.md byte-for-byte parity vs a fresh fold (mirrors bring_core cmd_check).
    want = roll_status_text(actions, entries, events, today, now_ts)
    try:
        with open(p["roll_status"], encoding="utf-8") as f:
            have = f.read()
    except OSError:
        have = ""
    if have != want:
        violations.append("(g) ROLL-STATUS.md drift — stale vs fold. Run `roll-status`.")
    if violations:
        for msg in violations:
            print(f"roll-check: FAIL {msg}")
        return 1
    print("roll-check: OK — conformant (a–f) + ROLL-STATUS parity (g)")
    return 0


def _resolve_now(a):
    now_ts_str = getattr(a, "now_ts", None)
    now_ts = _parse_iso(now_ts_str) if now_ts_str else _utc_now()
    now_str = getattr(a, "now", None)
    if now_str:
        today = datetime.date.fromisoformat(now_str)
    elif now_ts is not None:
        today = now_ts.date()
    else:
        today = datetime.date.today()
    return today, now_ts


def main(argv=None):
    p = argparse.ArgumentParser(description="Kata Harness roll core (see SPEC.md)")
    # --root/--now/--now-ts live on the TOP parser (before the verb), matching
    # bring_core.py and the plugin injector's `roll_core.py --root <r> roll-status` call.
    p.add_argument("--root", default=os.environ.get("BRING_ROOT", "."),
                   help="project root containing bring/ (default: cwd or $BRING_ROOT)")
    p.add_argument("--now", default=None, help="override today (YYYY-MM-DD, for tests)")
    p.add_argument("--now-ts", dest="now_ts", default=None,
                   help="override now (ISO8601, for deterministic timer/sub-day tests)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("roll-start", help="open a bounded roll (requires a target)")
    g = sp.add_mutually_exclusive_group(required=True)      # invariant #6: a target is required
    g.add_argument("--reps", type=int, help="rep-count target")
    g.add_argument("--minutes", type=int, help="duration target (minutes)")
    sp.add_argument("--cadence", default="open", help="default per-rep duration: 25m | open")
    sp.add_argument("--timer", action="store_true", help="opt the count-up/down display on")
    sp.add_argument("--session-id", dest="session_id", default=None)

    sub.add_parser("roll-tick", help="surface + stage exactly one bring")

    rr = sub.add_parser("roll-resolve", help="log the outcome (human executed)")
    rr.add_argument("--kind", required=True, choices=TERMINAL)
    rr.add_argument("--note", default="")

    rs = sub.add_parser("roll-skip", help="conscious decline (reason required)")
    rs.add_argument("--note", required=True)                 # invariant #3

    sub.add_parser("roll-elapse", help="window passed; bring stays open")
    sub.add_parser("roll-pause", help="hold the session")
    sub.add_parser("roll-resume", help="continue a paused session")
    sub.add_parser("roll-abort", help="end the session early (terminal)")
    sub.add_parser("roll-status", help="regenerate + print the roll face")
    sub.add_parser("roll-check", help="conformance + parity gate (exit 1 on drift)")

    a = p.parse_args(argv)
    today, now_ts = _resolve_now(a)
    root = os.path.abspath(a.root)
    dispatch = {
        "roll-start": cmd_roll_start, "roll-tick": cmd_roll_tick,
        "roll-resolve": cmd_roll_resolve, "roll-skip": cmd_roll_skip,
        "roll-elapse": cmd_roll_elapse, "roll-pause": cmd_roll_pause,
        "roll-resume": cmd_roll_resume, "roll-abort": cmd_roll_abort,
        "roll-status": cmd_roll_status, "roll-check": cmd_roll_check,
    }
    return dispatch[a.cmd](root, a, today, now_ts)


if __name__ == "__main__":
    sys.exit(main())
