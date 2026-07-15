#!/usr/bin/env python3
"""SessionStart adapter: report the active kata roll's status (report-only).

Speaks only when this project runs the bring queue AND has started a roll AND
that roll's most recent ledger event is not yet terminal (completed/aborted)
— i.e. a session is actually open or paused right now. This is a status
surface, not a daily nag: bring-loop's own SessionStart brief already owns
the "something every session" job (SPEC.md's Claude Code adapter section,
Coexistence).

REPORT-ONLY, always: this calls roll_core.py's read-only `roll-status` verb
(which reads/regenerates ROLL-STATUS.md) — never a verb that appends an
event. The only "logic" here is a one-line peek at the ledger's last event
tag, used only to decide whether to speak; no tick/target/cadence fold is
reimplemented — that stays in roll_core.py.

Fail-open contract: any error prints nothing and exits 0 (same contract as
bring-injector.py).
"""
import json
import os
import subprocess
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(PLUGIN_ROOT)
# roll_core.py may ship alongside this plugin (installed layout, mirroring
# bring_core.py's own convention) or one level up under the source repo's
# scripts/ (dev checkout layout, per SPEC.md's file manifest) — try both,
# first match wins. Either way it is only ever invoked, never reimplemented.
CORE_CANDIDATES = [
    os.path.join(REPO_ROOT, "scripts", "roll_core.py"),
    os.path.join(PLUGIN_ROOT, "scripts", "roll_core.py"),
]
TERMINAL_EVENTS = ("completed", "aborted")

NOTE = (" NOTE TO AGENT: this is a REPORT-ONLY roll status — surface it, "
        "nothing more. It never starts, ticks, resolves, skips, or elapses "
        "anything by itself. Ticks are operator-invoked only, via the "
        "kata-harness skill or a host-supplied /loop pointed at roll-tick — "
        "never automatic.")


def main():
    root = os.getcwd()
    if not os.path.isdir(os.path.join(root, "bring")):
        return  # project doesn't run the bring queue at all
    ledger_path = os.path.join(root, "bring", "roll-ledger.jsonl")
    if not os.path.exists(ledger_path):
        return  # bring-loop runs here, but no roll has ever started

    last_event = None
    with open(ledger_path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if raw:
                last_event = json.loads(raw).get("event")
    if last_event is None or last_event in TERMINAL_EVENTS:
        return  # no session open right now — nothing to report

    line = ""
    core = next((c for c in CORE_CANDIDATES if os.path.exists(c)), None)
    if core:
        try:
            r = subprocess.run([sys.executable, core, "--root", root, "roll-status"],
                               capture_output=True, text=True, timeout=8)
            if r.returncode == 0:
                line = (r.stdout or "").strip()
        except (OSError, subprocess.SubprocessError):
            pass

    if not line:
        try:
            with open(os.path.join(root, "bring", "ROLL-STATUS.md"), encoding="utf-8") as f:
                line = f.read().strip()
        except OSError:
            pass
    if not line:
        return

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": line + NOTE}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
