#!/usr/bin/env python3
"""Stop adapter: one deterministic line if today's bring went untouched.

Advisory only, never blocks, exits 0 always. Silent when: the project doesn't
run the loop, the queue is clear, or today already has a ledger entry (any
kind — a logged skip earns silence too; that's invariant #3).
"""
import datetime
import json
import os
import subprocess
import sys

CORE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "scripts", "bring_core.py")


def main():
    root = os.getcwd()
    if not os.path.exists(os.path.join(root, "bring", "actions.md")):
        return
    today = datetime.date.today().isoformat()
    try:
        with open(os.path.join(root, "bring", "ledger.jsonl"), encoding="utf-8") as f:
            if any(f'"date": "{today}"' in line or f'"date":"{today}"' in line for line in f):
                return
    except OSError:
        pass
    r = subprocess.run([sys.executable, CORE, "--root", root, "brief", "--json"],
                       capture_output=True, text=True, timeout=8)
    try:
        top = json.loads(r.stdout).get("top")
    except (json.JSONDecodeError, AttributeError):
        return
    if not top:
        return
    sys.stderr.write(
        f"bring-loop: today's bring went untouched — [{top['kind']}] {top['id']}: {top['title']}. "
        "Next session: ask to 'bring it' (stage only), or log a conscious skip with a reason.\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
