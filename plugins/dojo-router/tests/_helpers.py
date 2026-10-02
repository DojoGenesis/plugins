"""Shared test helpers: run a hook script the way the engine does, with a scrubbed environment."""
import itertools
import json
import os
import subprocess
import sys
import tempfile

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(TESTS_DIR)
HOOKS_DIR = os.path.join(PLUGIN_ROOT, "hooks")
FIXTURES_DIR = os.path.join(TESTS_DIR, "fixtures")
_COUNTER = itertools.count(1)


def fresh_session():
    """A session id no earlier test run used, so once-per-session state never leaks between cases."""
    return "sess-%d-%d" % (os.getpid(), next(_COUNTER))

if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)


def run_hook(script, payload=None, env=None, raw=None, timeout=10, data_dir=None, home=None):
    """Run hooks/<script> in a clean environment (the equivalent of env -i PATH=/usr/bin:/bin HOME=...).

    payload is JSON-encoded to stdin unless raw (str or bytes) is given. Returns (returncode, stdout, stderr).
    """
    # PYTHONDONTWRITEBYTECODE keeps the hook runs from leaving a __pycache__ folder inside the plugin.
    clean = {"PATH": "/usr/bin:/bin", "HOME": home or tempfile.gettempdir(), "PYTHONDONTWRITEBYTECODE": "1"}
    if data_dir:
        clean["CLAUDE_PLUGIN_DATA"] = data_dir
    if env:
        clean.update(env)
    if raw is None:
        raw = json.dumps(payload)
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    proc = subprocess.run(
        [sys.executable, os.path.join(HOOKS_DIR, script)],
        input=raw,
        env=clean,
        capture_output=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


def agent_payload(subagent_type="__unset__", model="__unset__", session_id="__fresh__", tool_name="Agent", cwd=None, **extra):
    tool_input = {"description": "look around", "prompt": "find the thing"}
    if subagent_type != "__unset__":
        tool_input["subagent_type"] = subagent_type
    if model != "__unset__":
        tool_input["model"] = model
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input}
    if session_id == "__fresh__":
        session_id = fresh_session()
    if session_id is not None:
        payload["session_id"] = session_id
    if cwd is not None:
        payload["cwd"] = cwd
    payload.update(extra)
    return payload


def workflow_payload(script=None, script_path=None, name=None, session_id="__fresh__", cwd=None):
    tool_input = {}
    if script is not None:
        tool_input["script"] = script
    if script_path is not None:
        tool_input["scriptPath"] = script_path
    if name is not None:
        tool_input["name"] = name
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Workflow", "tool_input": tool_input}
    if session_id == "__fresh__":
        session_id = fresh_session()
    if session_id is not None:
        payload["session_id"] = session_id
    if cwd is not None:
        payload["cwd"] = cwd
    return payload


def parse(stdout):
    return json.loads(stdout) if stdout.strip() else None
