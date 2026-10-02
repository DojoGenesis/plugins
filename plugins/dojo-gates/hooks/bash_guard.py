#!/usr/bin/env python3
"""dojo-gates: PreToolUse(Bash) entry point.

Runs the Bash guards in order (staging, pushed-rewrite, secret-print, token-url,
mac-timeout, masked-exit). The first deny wins; warnings are collected and
only emitted when nothing denies. Fails open: any error means no output, exit 0.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_MAX_CMD = 512 * 1024
_KEEP = 128 * 1024


def main():
    from _common import deny, killed, read_payload, warn

    if killed():
        return
    payload = read_payload()
    if payload is None:
        return
    name = payload.get("tool_name")
    if name is not None and name != "Bash":
        return
    ti = payload.get("tool_input")
    if not isinstance(ti, dict):
        return
    cmd = ti.get("command")
    if not isinstance(cmd, str) or not cmd.strip():
        return
    if len(cmd) > _MAX_CMD:
        cmd = cmd[:_KEEP] + "\n" + cmd[-_KEEP:]

    from _guards import GUARDS, Ctx
    from _shell import all_segments

    ctx = Ctx(cmd, all_segments(cmd), payload)
    warns = []
    for gid, fn in GUARDS:
        if killed(gid):
            continue
        try:
            res = fn(ctx)
        except Exception:
            res = None
        if not res:
            continue
        kind, msg = res
        if kind == "deny":
            deny(msg)
            return
        warns.append(msg)
    if warns:
        warn("\n".join(warns))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
