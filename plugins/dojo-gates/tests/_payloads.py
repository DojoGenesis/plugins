"""Hand-written hook payloads and a subprocess runner for the dojo-gates tests.

Payloads are written by hand here (never produced by the code under test).
Token-shaped strings are built at runtime so secret scanners stay quiet.
Hooks are launched the way Claude Code launches them: a fresh process with a
minimal environment (no inherited PATH, HOME or git configuration).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(HERE)
HOOKS = os.path.join(PLUGIN_ROOT, "hooks")

# The interpreter the hook command (`python3` under PATH=/usr/bin:/bin) resolves to.
PY = "/usr/bin/python3" if os.path.exists("/usr/bin/python3") else sys.executable

SCRIPTS = {
    "bash_guard": os.path.join(HOOKS, "bash_guard.py"),
    "read_guard": os.path.join(HOOKS, "read_guard.py"),
    "claude_md_reach": os.path.join(HOOKS, "claude_md_reach.py"),
    "bash_after": os.path.join(HOOKS, "bash_after.py"),
}

# What a deny or note must never contain: it could re-trigger config-first.
TRIGGER = re.compile(
    r"\b401\b|\b403\b|ECONNREFUSED|command not found|No such file or directory"
)


# -- payload builders ----------------------------------------------------------

def pre_bash(cmd, cwd="/work/proj", session="s-test"):
    return {
        "session_id": session,
        "transcript_path": "/work/none.jsonl",
        "cwd": cwd,
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": cmd},
    }


def post_bash(cmd, stdout="", stderr="", session="s-test", interrupted=False, **extra):
    p = {
        "session_id": session,
        "cwd": "/work/proj",
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": cmd},
        "tool_response": {"stdout": stdout, "stderr": stderr, "interrupted": interrupted},
    }
    p.update(extra)
    return p


def post_fail(cmd, error, session="s-test", **extra):
    p = {
        "session_id": session,
        "cwd": "/work/proj",
        "hook_event_name": "PostToolUseFailure",
        "tool_name": "Bash",
        "tool_input": {"command": cmd},
        "error": error,
    }
    p.update(extra)
    return p


def pre_read(path, cwd="/work/proj", session="s-test", **tool_input):
    ti = {"file_path": path}
    ti.update(tool_input)
    return {
        "session_id": session,
        "cwd": cwd,
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": ti,
    }


def pre_edit(path, tool="Edit", cwd="/work/proj", session="s-test", transcript=None):
    return {
        "session_id": session,
        "transcript_path": transcript or "/work/none.jsonl",
        "cwd": cwd,
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"file_path": path},
    }


def instructions_loaded(path, session="s-test", reason="nested_traversal"):
    return {
        "session_id": session,
        "cwd": "/work/proj",
        "hook_event_name": "InstructionsLoaded",
        "file_path": path,
        "memory_type": "Project",
        "load_reason": reason,
    }


# -- token-shaped strings, built at runtime ---------------------------------------

def tok_github():
    return "gh" + "p_" + "A" * 36


def tok_github_oauth():
    return "gh" + "o_" + "B" * 36


def tok_github_pat():
    return "github" + "_pat_" + "C" * 40


def tok_gitlab():
    return "gl" + "pat-" + "D" * 24


def tok_sk():
    return "s" + "k-" + "E" * 30


def tok_sk_ant():
    return "s" + "k-ant-" + "F" * 30


def tok_slack():
    return "xo" + "xb-" + "1234567890-abcdef"


# -- running a hook ------------------------------------------------------------------

def base_env(**extra):
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": tempfile.gettempdir(),
        "PYTHONDONTWRITEBYTECODE": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    env.update(extra)
    return env


class Result(object):
    def __init__(self, code, out, err):
        self.code = code
        self.out = out
        self.err = err
        try:
            self.json = json.loads(out) if out.strip() else None
        except ValueError:
            self.json = None

    @property
    def hso(self):
        return (self.json or {}).get("hookSpecificOutput") or {}

    @property
    def decision(self):
        return self.hso.get("permissionDecision")

    @property
    def reason(self):
        return self.hso.get("permissionDecisionReason", "")

    @property
    def context(self):
        return self.hso.get("additionalContext", "")


def run_hook(script, payload=None, env=None, raw=None, timeout=20):
    """Run a hook script. payload is JSON-encoded; raw (bytes or str) overrides it."""
    path = SCRIPTS.get(script, script)
    if raw is None:
        raw = json.dumps(payload)
    if isinstance(raw, str):
        raw = raw.encode("utf-8", "surrogateescape")
    p = subprocess.run(
        [PY, path],
        input=raw,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env if env is not None else base_env(),
        timeout=timeout,
    )
    return Result(p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace"))


# -- throwaway git repositories, built with plumbing only (no hooks run) ---------------

class Repo(object):
    """A repository assembled with hash-object, mktree, commit-tree and update-ref."""

    def __init__(self, root):
        self.root = root
        self.env = {
            "PATH": "/usr/bin:/bin",
            "HOME": root,
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
        }
        self.git(["init", "-q", "-b", "main"])

    def git(self, args, stdin=None):
        p = subprocess.run(
            ["git"] + args,
            cwd=self.root,
            env=self.env,
            input=stdin.encode() if stdin is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if p.returncode != 0:
            raise RuntimeError("git %s failed: %s" % (args, p.stderr.decode()))
        return p.stdout.decode().strip()

    def commit(self, msg, parent=None):
        blob = self.git(["hash-object", "-w", "--stdin"], stdin=msg + "\n")
        tree = self.git(["mktree"], stdin="100644 blob %s\tf.txt\n" % blob)
        args = ["commit-tree", tree, "-m", msg]
        if parent:
            args += ["-p", parent]
        return self.git(args)

    def ref(self, name, sha):
        self.git(["update-ref", name, sha])

    def head(self, sha):
        self.ref("refs/heads/main", sha)


def make_pushed_repo(root):
    """c0 <- c1 <- c2; main = c2 = origin/main (HEAD is pushed)."""
    r = Repo(root)
    c0 = r.commit("c0")
    c1 = r.commit("c1", c0)
    c2 = r.commit("c2", c1)
    r.head(c2)
    r.ref("refs/remotes/origin/main", c2)
    return r, (c0, c1, c2)


def make_half_pushed_repo(root):
    """c0 <- c1 <- c2; origin/main = c1; main = c2 (HEAD unpushed, parent pushed)."""
    r = Repo(root)
    c0 = r.commit("c0")
    c1 = r.commit("c1", c0)
    c2 = r.commit("c2", c1)
    r.head(c2)
    r.ref("refs/remotes/origin/main", c1)
    return r, (c0, c1, c2)


def make_local_repo(root):
    """c0 <- c1 <- c2 with no remote refs at all."""
    r = Repo(root)
    c0 = r.commit("c0")
    c1 = r.commit("c1", c0)
    c2 = r.commit("c2", c1)
    r.head(c2)
    return r, (c0, c1, c2)


def make_amended_repo(root):
    """origin/main = c2 (pushed); local main = c2b, a sibling of c2 (amended away)."""
    r = Repo(root)
    c0 = r.commit("c0")
    c1 = r.commit("c1", c0)
    c2 = r.commit("c2", c1)
    c2b = r.commit("c2 amended", c1)
    r.head(c2b)
    r.ref("refs/remotes/origin/main", c2)
    return r, (c0, c1, c2, c2b)


def make_fastforward_repo(root):
    """origin/main = c1 is an ancestor of local main = c2."""
    r = Repo(root)
    c0 = r.commit("c0")
    c1 = r.commit("c1", c0)
    c2 = r.commit("c2", c1)
    r.head(c2)
    r.ref("refs/remotes/origin/main", c1)
    return r, (c0, c1, c2)


def tmpdir():
    d = tempfile.mkdtemp(prefix="dg")
    return d


def rmtree(d):
    shutil.rmtree(d, ignore_errors=True)
