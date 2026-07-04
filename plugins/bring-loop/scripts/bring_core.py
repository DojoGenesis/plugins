#!/usr/bin/env python3
"""bring_core.py — the Bring Loop, harness-agnostic core. Stdlib only, no network.

THE EFFECT (origin: Cruz Romero Morales' "BringItCruz!" operator persona —
"Built it, now bring it"): agentic tooling amplifies your build loop and leaves
your outward loop — sends, decisions, closes — ungated, so the gap between what
you make and what you bring widens. This loop gates the outward step the same
way builders gate the inward one, without taking it over.

THE CONTRACT (invariants; see SPEC.md):
  1. ONE action per day is surfaced — never a list. Queue-paralysis is the enemy.
  2. Surface + stage ONLY. The human executes the send/decision. Nothing here
     auto-sends anything, ever.
  3. A conscious skip is a valid, logged rep. Declined beats expired.
  4. Streams are measured separately (sent/decided/closed/shipped/skipped) —
     never blended into one score.
  5. Ownership split: humans (and their agents) write bring/actions.md; this
     tool NEVER edits it. The tool owns ledger.jsonl (append-only) and
     SCOREBOARD.md (generated). One source per concern.

FILES (under <root>/bring/):
  actions.md    — the queue source. Human face AND agent face of intent.
  ledger.jsonl  — outcomes, append-only. Agent face of history.
  SCOREBOARD.md — generated human face of history. `check` gates its freshness.

USAGE:
  python bring_core.py init                       # scaffold bring/ in this project
  python bring_core.py brief [--json]             # today's ONE action (for hooks/MOTD)
  python bring_core.py log sent --id july-invoice # record an outcome
  python bring_core.py status                     # streams + streak
  python bring_core.py scoreboard                 # regenerate SCOREBOARD.md
  python bring_core.py check                      # parity gate (exit 1 = stale/broken)
All commands accept --root <dir> (default: cwd) and --now YYYY-MM-DD (tests).
"""
from __future__ import annotations
import argparse
import datetime
import json
import os
import re
import sys

KINDS = ("sent", "decided", "closed", "shipped", "skipped")
TERMINAL = ("sent", "decided", "closed", "shipped")
DEFAULT_SEND_CAP = 5
DECK_SIZE = 2

ACTIONS_TEMPLATE = """---
weekly_send_cap: 5
weekends_free: true
---

# Bring queue

One `##` section per outward action. You (or your agent) write this file; the
loop only reads it. Keys: `kind:` send|decide|close|ship · `due:` YYYY-MM-DD ·
`id:` stable slug (optional, defaults from the title) · `link:` · `note:`.
Done actions disappear from the queue once their outcome is logged — prune the
text whenever you feel like it.

## Example: send the overdue reply
kind: send
due: 2026-01-01
note: replace me with a real action, then delete this example
"""


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# pure logic
# ---------------------------------------------------------------------------

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


def brief_text(top, deck, counts, stk, cap, today_logged):
    if not top:
        return ("BRING LOOP: queue clear — add the next outward action to bring/actions.md. "
                f"Week: sent {counts['sent']}/{cap}, decided {counts['decided']}, "
                f"closed {counts['closed']}, shipped {counts['shipped']}. Streak {stk}d.")
    due = f" (due {top['due']})" if top.get("due") else ""
    state = "already logged today — on deck for tomorrow" if today_logged else "not yet brought today"
    deck_s = "; deck: " + ", ".join(d["id"] for d in deck) if deck else ""
    return (f"TODAY'S BRING ({state}): [{top['kind']}] {top['id']} — {top['title']}{due}{deck_s}. "
            f"Week: sent {counts['sent']}/{cap}, decided {counts['decided']}, closed {counts['closed']}, "
            f"shipped {counts['shipped']}; streak {stk}d. Contract: surface + stage only — the human "
            "executes; log with `python bring_core.py log <sent|decided|closed|shipped|skipped> --id "
            f"{top['id']}`. A logged skip is a valid rep.")


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


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def paths(root):
    b = os.path.join(root, "bring")
    return b, os.path.join(b, "actions.md"), os.path.join(b, "ledger.jsonl"), os.path.join(b, "SCOREBOARD.md")


def load_all(root):
    _, actions_p, ledger_p, _ = paths(root)
    try:
        with open(actions_p, encoding="utf-8") as f:
            config, actions = parse_actions(f.read())
    except OSError:
        config, actions = {"weekly_send_cap": DEFAULT_SEND_CAP, "weekends_free": True}, []
    return config, actions, load_ledger(ledger_p)


def cmd_init(root, _a, _today):
    b, actions_p, ledger_p, _ = paths(root)
    os.makedirs(b, exist_ok=True)
    if not os.path.exists(actions_p):
        with open(actions_p, "w", encoding="utf-8") as f:
            f.write(ACTIONS_TEMPLATE)
        print(f"created {actions_p}")
    else:
        print(f"exists  {actions_p}")
    if not os.path.exists(ledger_p):
        open(ledger_p, "w", encoding="utf-8").close()
        print(f"created {ledger_p}")
    print("Next: edit bring/actions.md, then wire `python bring_core.py brief` into your "
          "session start (Claude Code plugin, shell rc, editor task — anything that prints).")
    return 0


def cmd_brief(root, a, today):
    config, actions, entries = load_all(root)
    opn = open_actions(actions, entries, today)
    top, deck = pick(opn)
    counts = week_counts(entries, today)
    stk = streak(entries, today, config["weekends_free"])
    today_logged = any(e.get("date") == today.isoformat() for e in entries)
    if getattr(a, "json", False):
        print(json.dumps({"date": today.isoformat(), "top": top and {k: top[k] for k in ("id", "title", "kind", "due", "link", "note")},
                          "deck": [d["id"] for d in deck], "week": counts, "streak": stk,
                          "cap": config["weekly_send_cap"]}, ensure_ascii=False, default=str))
    else:
        print(brief_text(top, deck, counts, stk, config["weekly_send_cap"], today_logged))
    return 0


def cmd_log(root, a, today):
    _, _, ledger_p, _ = paths(root)
    os.makedirs(os.path.dirname(ledger_p), exist_ok=True)
    e = {"utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "date": today.isoformat(), "kind": a.kind, "id": a.id or "", "note": a.note or ""}
    with open(ledger_p, "a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    cmd_scoreboard(root, a, today)      # keep the human face fresh on every log
    print(f"logged {a.kind} {a.id or ''}".rstrip())
    return cmd_status(root, a, today)


def cmd_status(root, _a, today):
    config, _actions, entries = load_all(root)
    c = week_counts(entries, today)
    stk = streak(entries, today, config["weekends_free"])
    print(f"week: sent {c['sent']}/{config['weekly_send_cap']} · decided {c['decided']} · "
          f"closed {c['closed']} · shipped {c['shipped']} · skips {c['skipped']} · streak {stk}d")
    return 0


def cmd_scoreboard(root, _a, today):
    config, actions, entries = load_all(root)
    _, _, _, sb_p = paths(root)
    os.makedirs(os.path.dirname(sb_p), exist_ok=True)
    with open(sb_p, "w", encoding="utf-8") as f:
        f.write(scoreboard_text(config, actions, entries, today))
    print(f"scoreboard -> {sb_p}")
    return 0


def cmd_check(root, _a, today):
    """Parity gate: SCOREBOARD.md must match today's regeneration. Exit 1 on drift."""
    config, actions, entries = load_all(root)
    _, actions_p, _, sb_p = paths(root)
    if not os.path.exists(actions_p):
        print("check: no bring/actions.md — run `init` first")
        return 1
    want = scoreboard_text(config, actions, entries, today)
    try:
        with open(sb_p, encoding="utf-8") as f:
            have = f.read()
    except OSError:
        have = ""
    if have != want:
        print("check: DRIFT — SCOREBOARD.md is stale vs actions+ledger. Run `scoreboard`.")
        return 1
    print("check: OK — surfaces agree")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Bring Loop core (see SPEC.md)")
    p.add_argument("--root", default=os.environ.get("BRING_ROOT", "."),
                   help="project root containing bring/ (default: cwd or $BRING_ROOT)")
    p.add_argument("--now", default=None, help="override today (YYYY-MM-DD, for tests)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    b = sub.add_parser("brief")
    b.add_argument("--json", action="store_true")
    lg = sub.add_parser("log")
    lg.add_argument("kind", choices=KINDS)
    lg.add_argument("--id", default="")
    lg.add_argument("--note", default="")
    sub.add_parser("status")
    sub.add_parser("scoreboard")
    sub.add_parser("check")
    a = p.parse_args(argv)

    today = datetime.date.fromisoformat(a.now) if a.now else datetime.date.today()
    root = os.path.abspath(a.root)
    return {"init": cmd_init, "brief": cmd_brief, "log": cmd_log, "status": cmd_status,
            "scoreboard": cmd_scoreboard, "check": cmd_check}[a.cmd](root, a, today)


if __name__ == "__main__":
    sys.exit(main())
