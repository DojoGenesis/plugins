#!/usr/bin/env python3
"""dojo-gates: PreToolUse(Read) big-read guard.

Denies a Read of a regular file over 256 KB (262144 bytes) when neither
`offset` nor `limit` is given, and points at grep / a ranged Read instead.
Claude Code has its own size limit on Read; this refuses earlier and names
a narrower route (grep, then a ranged Read). Fails open.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LIMIT_BYTES = 262144
_SKIP_EXT = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ipynb")


def main():
    from _common import deny, killed, message, override, read_payload

    if killed("big-read"):
        return
    payload = read_payload()
    if payload is None:
        return
    name = payload.get("tool_name")
    if name is not None and name != "Read":
        return
    ti = payload.get("tool_input")
    if not isinstance(ti, dict):
        return
    path = ti.get("file_path")
    if not isinstance(path, str) or not path:
        return
    if ti.get("offset") is not None or ti.get("limit") is not None:
        return
    if path.lower().endswith(_SKIP_EXT):
        return
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            return
        path = os.path.join(cwd, path)
    try:
        if not os.path.isfile(path):
            return
        size = os.path.getsize(path)
    except OSError:
        return
    if size <= LIMIT_BYTES:
        return
    deny(
        message(
            "big-read",
            "%s is %d KB, and reading all of it puts the whole file in context" % (os.path.basename(path), size // 1024),
            "Search first (`grep -n 'pattern' <path>`), then Read with `offset` and `limit` around the lines you need. "
            + override("big-read"),
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
