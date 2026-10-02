"""Shared fixtures for the dojo-meter tests: hand-written transcript lines in a temp config directory."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

TESTS = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(TESTS)
SCRIPTS = os.path.join(PLUGIN_ROOT, "scripts")
COST = os.path.join(SCRIPTS, "cost.py")
# Run the script under the system interpreter (3.9 on macOS) when there is one: that is the floor we promise.
PY = "/usr/bin/python3" if os.path.exists("/usr/bin/python3") else sys.executable

sys.path.insert(0, SCRIPTS)

M = 1000000
NOW = "2026-10-02T15:00:00Z"  # 10:00 on 2026-10-02 in America/Chicago
CANARY = "-tmp-zz-meter-canary"  # a project folder name no output may ever contain


def entry(msg_id="m1", request_id="r1", model="claude-sonnet-5-5", inp=0, out=0, read=0, write=0, split=None,
          ts="2026-10-02T12:00:00.000Z", sidechain=False, block="text", kind="assistant", usage="default"):
    """One transcript line, shaped the way Claude Code writes an assistant line."""
    if usage == "default":
        usage = {
            "input_tokens": inp, "output_tokens": out,
            "cache_read_input_tokens": read, "cache_creation_input_tokens": write,
        }
        if split is not None:
            usage["cache_creation"] = {"ephemeral_5m_input_tokens": split[0], "ephemeral_1h_input_tokens": split[1]}
    message = {"id": msg_id, "type": "message", "role": "assistant", "model": model,
               "content": [{"type": block, "text": "x"}], "usage": usage}
    if msg_id is None:
        del message["id"]
    obj = {"type": kind, "timestamp": ts, "isSidechain": sidechain, "message": message}
    if request_id is not None:
        obj["requestId"] = request_id
    return json.dumps(obj)


class Fixture(object):
    """A fake Claude Code config directory: <root>/projects/<project>/..."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="dojo-meter-test-")
        self.projects = os.path.join(self.root, "projects")
        os.makedirs(self.projects)

    def write(self, rel, lines, mtime=None, raw=None):
        path = os.path.join(self.projects, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        mode = "wb" if raw is not None else "w"
        with open(path, mode) as handle:
            handle.write(raw if raw is not None else "\n".join(lines) + "\n")
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def cleanup(self):
        for dirpath, dirnames, filenames in os.walk(self.root):
            for name in dirnames + filenames:
                try:
                    os.chmod(os.path.join(dirpath, name), 0o755 if name in dirnames else 0o644)
                except OSError:
                    pass
        shutil.rmtree(self.root, ignore_errors=True)


def run_cost(fixture, *args, **kwargs):
    """Run scripts/cost.py as a subprocess under a bare environment. Returns (exit code, stdout, stderr)."""
    env = {"PATH": "/usr/bin:/bin", "HOME": fixture.root, "TZ": kwargs.get("tz", "UTC")}
    cmd = [PY, COST, "--root", fixture.root] + list(args)
    if kwargs.get("now", NOW):
        cmd += ["--now", kwargs.get("now", NOW)]
    proc = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


def run_json(fixture, *args, **kwargs):
    code, out, err = run_cost(fixture, "--json", *args, **kwargs)
    assert code == 0, (code, out, err)
    return json.loads(out)


def rows_by(data, who=None):
    return [r for r in data["rows"] if who is None or r["who"] == who]


def total(data, field, who=None):
    return sum(r[field] for r in rows_by(data, who))
