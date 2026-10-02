"""Shared helpers for the dojo-verify tests.

Transcript fixtures are written by hand here (never produced by the code under test), and the hook is run as a
subprocess the way the engine runs it: JSON on stdin, a small environment, exit code and stdout asserted.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(TESTS_DIR)
HOOK = os.path.join(PLUGIN_ROOT, "hooks", "stop_evidence.py")
SYSTEM_PYTHON = "/usr/bin/python3" if os.path.exists("/usr/bin/python3") else sys.executable

_counter = [0]


def uid():
    _counter[0] += 1
    return "u%06d" % _counter[0]


def load_hook_module():
    spec = importlib.util.spec_from_file_location("stop_evidence_under_test", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- transcript entries


def prompt(text, **extra):
    e = {
        "type": "user",
        "uuid": uid(),
        "isSidechain": False,
        "origin": {"kind": "human"},
        "message": {"role": "user", "content": text},
    }
    e.update(extra)
    return e


def legacy_prompt(text):
    """An older transcript: no origin field, plain string content."""
    return {"type": "user", "uuid": uid(), "isSidechain": False, "message": {"role": "user", "content": text}}


def meta_user(text, **extra):
    e = {"type": "user", "uuid": uid(), "isMeta": True, "isSidechain": False,
         "message": {"role": "user", "content": text}}
    e.update(extra)
    return e


def assistant_text(text, **extra):
    e = {"type": "assistant", "uuid": uid(), "isSidechain": False,
         "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}
    e.update(extra)
    return e


def assistant_thinking(text="hmm"):
    return {"type": "assistant", "uuid": uid(), "isSidechain": False,
            "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": text}]}}


def tool_use(tool_id, name, tool_input, **extra):
    e = {"type": "assistant", "uuid": uid(), "isSidechain": False,
         "message": {"role": "assistant", "content": [{"type": "tool_use", "id": tool_id, "name": name,
                                                       "input": tool_input}]}}
    e.update(extra)
    return e


def bash_use(tool_id, command, **extra_input):
    inp = {"command": command}
    inp.update(extra_input)
    return tool_use(tool_id, "Bash", inp)


def tool_result(tool_id, text, is_error=None, interrupted=None, **extra):
    block = {"type": "tool_result", "tool_use_id": tool_id, "content": text}
    if is_error is not None:
        block["is_error"] = is_error
    e = {"type": "user", "uuid": uid(), "isSidechain": False,
         "message": {"role": "user", "content": [block]}}
    if interrupted is not None:
        e["toolUseResult"] = {"stdout": text, "stderr": "", "interrupted": interrupted}
    e.update(extra)
    return e


def task_notification(tool_id, exit_code, description="npm test"):
    text = (
        "<task-notification>\n<task-id>bg1</task-id>\n<tool-use-id>%s</tool-use-id>\n"
        "<summary>Background command \"%s\" completed (exit code %d)</summary>\n</task-notification>"
        % (tool_id, description, exit_code)
    )
    return {"type": "user", "uuid": uid(), "isMeta": False, "isSidechain": False,
            "origin": {"kind": "task-notification"}, "message": {"role": "user", "content": text}}


def edit_use(tool_id, path="/work/app/src/main.py"):
    return tool_use(tool_id, "Edit", {"file_path": path, "old_string": "a", "new_string": "b"})


def passing_check(tool_id, command="pytest -q", output="3 passed in 0.1s"):
    return [bash_use(tool_id, command), tool_result(tool_id, output)]


def sidechain(entry):
    entry["isSidechain"] = True
    return entry


# --------------------------------------------------------------------------- running the hook


class Sandbox(object):
    """A temp project dir (to prove nothing is written there), a state dir and a transcript path."""

    def __init__(self, test):
        self.tmp = tempfile.TemporaryDirectory(prefix="dojo-verify-test-")
        test.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.project = os.path.join(self.root, "project")
        self.state = os.path.join(self.root, "state")
        self.tmpdir = os.path.join(self.root, "tmp")
        self.home = os.path.join(self.root, "home")
        for d in (self.project, self.state, self.tmpdir, self.home):
            os.mkdir(d)
        self.transcript = os.path.join(self.root, "transcript.jsonl")

    def write(self, entries, raw_tail=None):
        with open(self.transcript, "w") as fh:
            for e in entries:
                fh.write(json.dumps(e) + "\n")
            if raw_tail:
                fh.write(raw_tail)
        return self.transcript

    def payload(self, **kw):
        p = {
            "session_id": "sess-1",
            "transcript_path": self.transcript,
            "cwd": self.project,
            "hook_event_name": "Stop",
            "stop_hook_active": False,
        }
        p.update(kw)
        return p

    def env(self, **extra):
        env = {"PATH": "/usr/bin:/bin", "HOME": self.home, "CLAUDE_PLUGIN_DATA": self.state, "TMPDIR": self.tmpdir}
        for k, v in extra.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
        return env

    def project_listing(self):
        return sorted(os.listdir(self.project))


class Result(object):
    def __init__(self, proc):
        self.code = proc.returncode
        self.out = proc.stdout.decode("utf-8", "replace")
        self.err = proc.stderr.decode("utf-8", "replace")

    def json(self):
        return json.loads(self.out)

    @property
    def silent(self):
        return self.out == "" and self.err == "" and self.code == 0

    @property
    def blocked(self):
        if self.code != 0 or not self.out:
            return False
        data = json.loads(self.out)
        return data.get("decision") == "block"


def run_hook(stdin, env, cwd=None, python=None):
    """Run the hook as a subprocess. stdin is a dict (sent as JSON) or raw bytes."""
    data = stdin if isinstance(stdin, bytes) else json.dumps(stdin).encode("utf-8")
    proc = subprocess.run(
        [python or SYSTEM_PYTHON, HOOK],
        input=data,
        env=env,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    return Result(proc)
