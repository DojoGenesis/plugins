"""Shared helpers for the dojo-gates hook scripts.

Stdlib only, Python 3.9 safe. Every hook script fails open: on any problem it
prints nothing and exits 0.
"""
import json
import os
import re
import sys

PLUGIN = "dojo-gates"
_TRUE = ("1", "true", "yes", "on")


def _flag(name):
    return os.environ.get(name, "").strip().lower() in _TRUE


def skip_ids():
    """Guard ids named in DOJO_GATES_SKIP. Read only from the hook process
    environment, never from a command's text."""
    raw = os.environ.get("DOJO_GATES_SKIP", "")
    return set(p.strip().lower() for p in raw.split(",") if p.strip())


def killed(guard_id=None):
    """True when the whole suite, this plugin, or (given an id) that guard is off."""
    if _flag("DOJO_OFF") or _flag("DOJO_GATES_OFF"):
        return True
    if guard_id is not None and guard_id in skip_ids():
        return True
    return False


def read_payload():
    """The hook payload as a dict, or None for empty, invalid or non-dict input."""
    try:
        raw = sys.stdin.buffer.read()
    except Exception:
        return None
    if not raw or not raw.strip():
        return None
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _emit(obj):
    sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()


def deny(reason):
    _emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    )


def warn(message):
    _emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": message,
            },
            "systemMessage": message,
        }
    )


def post_context(event, text):
    _emit(
        {
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": text,
            }
        }
    )


def message(guard_id, what, how):
    """`dojo-gates: <id> — <what and why>. <how to proceed>`"""
    return "%s: %s — %s. %s" % (PLUGIN, guard_id, what.rstrip("."), how)


def override(guard_id):
    return (
        "To allow it on purpose, set DOJO_GATES_SKIP=%s in the environment "
        "Claude Code starts with (or under env in settings.json)." % guard_id
    )


# -- once per session -----------------------------------------------------------

def safe_id(value):
    s = re.sub(r"[^A-Za-z0-9_-]", "_", str(value))[:64]
    return s or "nosession"


def state_dir(session_id):
    import tempfile

    base_dir = os.environ.get("CLAUDE_PLUGIN_DATA") or tempfile.gettempdir()
    d = os.path.join(base_dir, "dojo-gates", safe_id(session_id))
    os.makedirs(d, exist_ok=True)
    return d


def once(session_id, key):
    """True the first time (session, key) is seen, False after. The marker is
    claimed with O_EXCL so parallel hooks emit once. False when state can't be
    written, so an unwritable disk makes a guard quiet rather than noisy."""
    try:
        import hashlib

        d = state_dir(session_id)
        name = re.sub(r"[^A-Za-z0-9_-]", "_", key)[:40]
        name += "." + hashlib.sha1(key.encode("utf-8", "replace")).hexdigest()[:12]
        fd = os.open(os.path.join(d, name), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        return True
    except Exception:
        return False


def session_of(payload):
    sid = payload.get("session_id") if isinstance(payload, dict) else None
    return sid if isinstance(sid, str) and sid else "nosession"
