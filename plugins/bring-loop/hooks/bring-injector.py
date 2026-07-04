#!/usr/bin/env python3
"""SessionStart adapter: inject today's bring into the session (offer register).

Only speaks when the current project actually runs the loop (a bring/actions.md
exists at the session cwd) — a plugin must not nag projects that never opted in.
Fail-open contract: any error prints nothing and exits 0.
"""
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
    r = subprocess.run([sys.executable, CORE, "--root", root, "brief"],
                       capture_output=True, text=True, timeout=8)
    line = (r.stdout or "").strip()
    if r.returncode != 0 or not line:
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": line + (" NOTE TO AGENT: honor the bring-loop contract "
                                     "(see the repo's bring/ + the bring skill): surface + stage only; "
                                     "log only on the human's word; one action, not the list.")}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
