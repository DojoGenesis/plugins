"""Shared fixtures for the suite tooling tests.

Everything here is hand-written text. Only synthetic home-directory paths are assembled
from fragments at run time, so this package never carries a literal path of that shape.
Denylist tests use synthetic terms only.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

LINT = os.path.join(SCRIPTS, "suite_lint.py")
DENY = os.path.join(SCRIPTS, "suite_denylist.py")
RELEASE = os.path.join(SCRIPTS, "release-check.sh")
PY39 = "/usr/bin/python3" if os.path.exists("/usr/bin/python3") else sys.executable
BASH = "/bin/bash" if os.path.exists("/bin/bash") else None

DELETE = object()


def frag(*parts):
    return "".join(parts)


# Machine-specific home paths, which suite_lint flags. Built at run time from fragments so
# this package never carries a literal path of that shape. Names of private projects, people
# and tools are not tested here at all: those live in local-only lists that only
# suite_denylist.py reads.
OP_PATH = frag("/Us", "ers/jdoe1/project")
OP_PATH_LINUX = frag("/ho", "me/jdoe1/project")
OP_PATH_WIN = frag("C:\\Us", "ers\\jdoe1")

SUITE_MEMBERS = [
    "dojo-protocol", "dojo-gates", "dojo-router", "dojo-meter",
    "dojo-verify", "dojo-flow", "dojo-doctor", "dojo-settle",
]

GATES_PROMISE = (
    "Deterministic guards for the mistakes that waste a day: blanket staging, "
    "rewriting pushed commits, printing secrets, oversized reads, silent probes."
)

SKILL = """---
name: lab
description: Use when a guard denies a command and you need its id or the override.
---

# lab

Short body. Run `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/guard.py"` to see it work.
"""

AGENT = """---
name: checker
description: Check one claim against the files and report what you found.
model: haiku
effort: low
tools: Read, Glob, Grep
maxTurns: 10
---

Check the claim. Report file and line.
"""

COMMAND = """---
description: Show which guards are active.
allowed-tools: Read
---

Show the guards.
"""

HOOK_PY = """import os
import sys

if os.environ.get("DOJO_OFF") == "1" or os.environ.get("DOJO_{UP}_OFF") == "1":
    sys.exit(0)
"""

WORKFLOW = """export const meta = {
  name: 'demo',
  description: 'A demo workflow.',
  phases: ['one'],
}
const r = await agent('look around', { model: 'haiku', label: 'scout' })
"""

TEST_PY = """import unittest


class T(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(True)
"""


def good_manifest(name):
    return {
        "name": name,
        "version": "0.1.0",
        "description": GATES_PROMISE if name == "dojo-gates" else "Fixture plugin used by the lint tests.",
        "author": {"name": "Dojo Genesis", "email": "maintainer@example.com"},
        "homepage": "https://dojogenesis.com/suite#" + name,
        "repository": "https://github.com/DojoGenesis/plugins",
        "license": "Apache-2.0",
        "keywords": ["guards", "hooks"],
        "userConfig": {
            "mode": {"type": "string", "title": "Mode", "description": "warn or block", "default": "warn", "options": ["warn", "block"]},
            "auto": {"type": "boolean", "title": "Auto", "description": "switch the mod on or off", "default": True},
        },
    }


def good_hooks():
    return {
        "description": "fixture hooks",
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/guard.py"', "timeout": 5}]}
            ]
        },
    }


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if isinstance(content, bytes) else "w"
    with open(path, mode) as fh:
        fh.write(content)


def make_plugin(repo, name="dojo-lab", overrides=None, manifest=None):
    """Write a plugin that is clean under every rule, then apply overrides.

    overrides: {relative path: str | bytes | DELETE}. manifest: {key: value | DELETE}.
    """
    root = os.path.join(repo, "plugins", name)
    shutil.rmtree(root, ignore_errors=True)
    up = name[len("dojo-"):].upper().replace("-", "_")
    m = good_manifest(name)
    for k, v in (manifest or {}).items():
        if v is DELETE:
            m.pop(k, None)
        else:
            m[k] = v
    files = {
        ".claude-plugin/plugin.json": json.dumps(m, indent=2),
        "README.md": "# %s\n\nFixture. Uses ${CLAUDE_PLUGIN_ROOT}/hooks/guard.py. Tested with Claude Code 2.1.286.\n" % name,
        "skills/lab/SKILL.md": SKILL,
        "agents/checker.md": AGENT,
        "commands/status.md": COMMAND,
        "hooks/hooks.json": json.dumps(good_hooks(), indent=2),
        "hooks/guard.py": HOOK_PY.replace("{UP}", up),
        "workflows/demo.js": WORKFLOW,
        "evals/first/case.yaml": "name: first\n",
        "tests/test_guard.py": TEST_PY,
    }
    for rel, content in (overrides or {}).items():
        if content is DELETE:
            files.pop(rel, None)
        else:
            files[rel] = content
    for rel, content in files.items():
        write(os.path.join(root, rel), content)
    return root


def suite_manifest(deps=None, **extra):
    m = {
        "name": "dojo-suite",
        "version": "0.1.0",
        "description": "Installs the eight Dojo suite plugins together.",
        "author": {"name": "Dojo Genesis", "email": "maintainer@example.com"},
        "homepage": "https://dojogenesis.com/suite#dojo-suite",
        "repository": "https://github.com/DojoGenesis/plugins",
        "license": "Apache-2.0",
        "dependencies": list(SUITE_MEMBERS) if deps is None else deps,
    }
    for k, v in extra.items():
        if v is DELETE:
            m.pop(k, None)
        else:
            m[k] = v
    return m


def make_suite(repo, manifest=None, member_dirs=None, listed=None, marketplace=True, files=None):
    """Write the dependency-only plugin, directories for its dependencies and a marketplace file.

    manifest: dict or None (the clean one). member_dirs: names that get a plugin directory
    (default: the eight). listed: names in marketplace.json (default: the eight plus the suite).
    """
    root = os.path.join(repo, "plugins", "dojo-suite")
    shutil.rmtree(root, ignore_errors=True)
    write(os.path.join(root, ".claude-plugin", "plugin.json"), json.dumps(manifest if manifest is not None else suite_manifest(), indent=2))
    for rel, content in (files or {}).items():
        write(os.path.join(root, rel), content)
    for n in (SUITE_MEMBERS if member_dirs is None else member_dirs):
        os.makedirs(os.path.join(repo, "plugins", n), exist_ok=True)
    mp = os.path.join(repo, ".claude-plugin", "marketplace.json")
    if marketplace is True:
        names = (SUITE_MEMBERS + ["dojo-suite"]) if listed is None else listed
        write(mp, json.dumps({"name": "fixture", "plugins": [{"name": n, "source": "./plugins/" + n} for n in names]}))
    elif isinstance(marketplace, str):
        write(mp, marketplace)
    elif os.path.exists(mp):
        os.remove(mp)
    return root


class Result(object):
    def __init__(self, rc, out, err):
        self.rc, self.out, self.err = rc, out, err
        self.lines = [l for l in out.splitlines() if l.strip()]

    def has(self, rule, path=None, line=None, text=None, sev=None):
        for l in self.lines:
            parts = l.split(":", 3)
            if len(parts) < 4:
                continue
            p, ln, ru, msg = parts[0], parts[1], parts[2], parts[3].strip()
            if ru != rule:
                continue
            if path is not None and path not in p:
                continue
            if line is not None and ln != str(line):
                continue
            if text is not None and text not in msg:
                continue
            if sev == "warning" and not msg.startswith("warning:"):
                continue
            if sev == "error" and msg.startswith("warning:"):
                continue
            return True
        return False


def clean_env(home):
    return {"PATH": "/usr/bin:/bin", "HOME": home}


class Base(unittest.TestCase):
    """Creates a temp repo and a temp HOME; cleans both up."""

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="suite-test-repo-")
        self.home = tempfile.mkdtemp(prefix="suite-test-home-")
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.addCleanup(shutil.rmtree, self.home, True)

    def plugin(self, name="dojo-lab", overrides=None, manifest=None):
        return make_plugin(self.repo, name, overrides, manifest)

    def lint(self, *args, **kw):
        env = clean_env(self.home)
        env.update(kw.get("env") or {})
        cmd = [kw.get("python", PY39), LINT, "--repo", self.repo] + list(args)
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=kw.get("cwd"))
        return Result(r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace"))

    def lint_plugin(self, name="dojo-lab", overrides=None, manifest=None, *args, **kw):
        self.plugin(name, overrides, manifest)
        return self.lint(name, *args, **kw)

    def no_pycache(self):
        found = []
        for d, dirs, files in os.walk(self.repo):
            for n in dirs + files:
                if n == "__pycache__" or n.endswith(".pyc"):
                    found.append(os.path.join(d, n))
        return found


def run_script(argv, env, cwd=None):
    r = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=cwd)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
