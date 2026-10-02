#!/usr/bin/env python3
"""dojo-gates: claude-md-reach (off unless the claude_md_reach option is true).

Two events share this script.

  InstructionsLoaded  records which instruction files Claude Code loaded this
                      session (per-session state, never inside the project).
  PreToolUse Write|Edit  on the first edit under a directory whose nearest
                      CLAUDE.md was never loaded, denies once and names the file
                      to Read.

A CLAUDE.md counts as loaded when it was recorded by InstructionsLoaded, or
when it sits at or above the directory the session started in (taken from the
first transcript entry that carries a `cwd`, with the payload's cwd as a
fallback). Fails open.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_MAX_BYTES = 8 * 1024 * 1024
_MAX_LINES = 50
_CHUNK = 1024 * 1024


def option_on():
    v = os.environ.get("CLAUDE_PLUGIN_OPTION_CLAUDE_MD_REACH", "")
    return v.strip().lower() in ("true", "1", "yes")


def startup_cwd(transcript_path, fallback):
    """First `cwd` in the transcript head (bounded), else the fallback."""
    if isinstance(transcript_path, str) and transcript_path:
        try:
            seen = 0
            lines = 0
            with open(transcript_path, "rb") as f:
                while seen < _MAX_BYTES and lines < _MAX_LINES:
                    line = f.readline(_CHUNK)
                    if not line:
                        break
                    seen += len(line)
                    if not line.endswith(b"\n") and len(line) >= _CHUNK:
                        continue  # a giant line: skip its fragments
                    lines += 1
                    try:
                        entry = json.loads(line.decode("utf-8", "replace"))
                    except Exception:
                        continue
                    if isinstance(entry, dict) and isinstance(entry.get("cwd"), str) and entry["cwd"]:
                        return entry["cwd"]
        except Exception:
            pass
    return fallback if isinstance(fallback, str) and fallback else None


def governing_file(start_dir):
    d = start_dir
    while True:
        for cand in (os.path.join(d, "CLAUDE.md"), os.path.join(d, ".claude", "CLAUDE.md")):
            if os.path.isfile(cand):
                return cand
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _loaded_set(session_id):
    from _common import state_dir

    out = set()
    try:
        with open(os.path.join(state_dir(session_id), "claude-md-loaded.txt"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.add(line)
    except Exception:
        pass
    return out


def record_loaded(payload):
    from _common import session_of, state_dir

    path = payload.get("file_path")
    if not isinstance(path, str) or not path:
        return
    real = os.path.realpath(path)
    with open(os.path.join(state_dir(session_of(payload)), "claude-md-loaded.txt"), "a", encoding="utf-8") as f:
        f.write(real + "\n")


def _under(child, parent):
    return child == parent or child.startswith(parent.rstrip(os.sep) + os.sep)


def check_edit(payload):
    from _common import deny, message, once, override, session_of

    ti = payload.get("tool_input")
    if not isinstance(ti, dict):
        return
    target = ti.get("file_path")
    if not isinstance(target, str) or not target:
        return
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    target = os.path.expanduser(target)
    if not os.path.isabs(target):
        if not cwd:
            return
        target = os.path.join(cwd, target)
    d = os.path.dirname(target)
    while d and not os.path.isdir(d):
        parent = os.path.dirname(d)
        if parent == d:
            return
        d = parent
    if not d:
        return
    gov = governing_file(os.path.realpath(d))
    if gov is None:
        return
    gov = os.path.realpath(gov)
    sid = session_of(payload)
    if gov in _loaded_set(sid):
        return
    gdir = os.path.dirname(gov)
    if os.path.basename(gdir) == ".claude":
        gdir = os.path.dirname(gdir)
    start = startup_cwd(payload.get("transcript_path"), cwd)
    if not start:
        return
    if _under(os.path.realpath(start), gdir):
        return
    if not once(sid, "reach:" + gov):
        return
    deny(
        message(
            "claude-md-reach",
            "%s governs this edit and wasn't loaded this session (it sits below where you started)" % gov,
            "Read that file first, then retry the edit; this is shown once per file per session. "
            + override("claude-md-reach"),
        )
    )


def main():
    from _common import killed, read_payload

    if killed("claude-md-reach") or not option_on():
        return
    payload = read_payload()
    if payload is None:
        return
    event = payload.get("hook_event_name")
    if event == "InstructionsLoaded":
        record_loaded(payload)
        return
    name = payload.get("tool_name")
    if name is not None and name not in ("Write", "Edit", "MultiEdit"):
        return
    check_edit(payload)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
