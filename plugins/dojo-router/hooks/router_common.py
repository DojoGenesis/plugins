"""Shared helpers for the dojo-router classic hooks.

Stdlib only, Python 3.9 safe. Every hook built on this fails open: any error means
exit 0 with no output. Nothing here touches the network, a model, or the user's project.
"""
import hashlib
import json
import os
import sys
import tempfile

TIERS = ("haiku", "sonnet", "opus")
MODES = ("warn", "block", "off")
DEFAULT_MODE = "warn"
DEFAULT_TIER = "sonnet"
DEFAULT_EXPLORE_TIER = "haiku"

# Role to alias table, as it appears in every message.
ROLE_TABLE = "haiku to look things up, sonnet to build or review, opus to judge"

MAX_STDIN_BYTES = 4 * 1024 * 1024


def read_payload():
    """Return the hook payload as a dict, or None when stdin is empty, unparseable or not an object."""
    try:
        raw = sys.stdin.buffer.read(MAX_STDIN_BYTES)
        data = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _truthy(value):
    return isinstance(value, str) and value.strip().lower() in ("1", "true", "yes")


def killed():
    """Kill switches, in order: DOJO_OFF (whole suite), then DOJO_ROUTER_OFF (this plugin)."""
    if _truthy(os.environ.get("DOJO_OFF")):
        return True
    if _truthy(os.environ.get("DOJO_ROUTER_OFF")):
        return True
    return False


def option(key):
    """A userConfig value as the engine exports it: CLAUDE_PLUGIN_OPTION_<KEY>, uppercased. None when absent."""
    return os.environ.get("CLAUDE_PLUGIN_OPTION_" + key.upper())


def _enum(value, allowed, default):
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in allowed:
            return cleaned
    return default


def get_mode():
    """warn | block | off. Anything else, or nothing, is warn (the manifest default)."""
    return _enum(option("mode"), MODES, DEFAULT_MODE)


def get_default_tier():
    return _enum(option("default_tier"), TIERS, DEFAULT_TIER)


def get_explore_tier():
    return _enum(option("explore_tier"), TIERS, DEFAULT_EXPLORE_TIER)


def state_dir():
    base = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not base or not base.strip():
        base = tempfile.gettempdir()
    return os.path.join(base, "dojo-router-state")


def first_time(session_id, finding):
    """True when this (session, finding) pair has not been reported yet, and records it.

    One marker file per key, created with O_EXCL so parallel dispatches in one message cannot
    both win. The key is a hash, so a hostile session id or finding cannot escape the state
    directory. When there is no usable session id or the directory is not writable this
    returns True every time: warn again rather than stay silent.
    """
    if not isinstance(session_id, str) or not session_id.strip():
        return True
    try:
        key = hashlib.sha256((session_id + "\0" + str(finding)).encode("utf-8", "replace")).hexdigest()
        directory = state_dir()
        os.makedirs(directory, exist_ok=True)
        fd = os.open(os.path.join(directory, key), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception:
        return True


def emit(obj):
    sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()


def emit_warn(text):
    """Warn without deciding anything: context for the model plus a message for the person.

    No permissionDecision key on purpose: an explicit allow would skip the person's normal
    permission prompt for the call.
    """
    emit({
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text},
        "systemMessage": text,
    })


def emit_deny(text):
    emit({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": text,
        },
        "systemMessage": text,
    })


def safe_label(value, limit=60):
    """Make an untrusted string safe to quote in a message."""
    out = []
    for ch in str(value)[:limit]:
        out.append(ch if (ch.isalnum() or ch in " _.-") else "_")
    return "".join(out)


def run(fn):
    """Run a hook body; any failure is a silent exit 0."""
    try:
        fn()
    except SystemExit:
        raise
    except BaseException:
        pass
    sys.exit(0)
