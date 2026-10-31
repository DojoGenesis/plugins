"""Tests for scripts/always_on.py, with a stand-in claude binary so no real CLI is needed."""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(SCRIPTS)
SCRIPT = os.path.join(SCRIPTS, "always_on.py")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import always_on  # noqa: E402

# Prints the "Always-on:" line that `claude --plugin-dir DIR plugin details NAME` prints,
# with the number read from DIR/listing.txt.
FAKE_CLAUDE = """#!/usr/bin/env python3
import sys
d = sys.argv[sys.argv.index("--plugin-dir") + 1]
n = open(d + "/listing.txt").read().strip()
print("Projected token cost")
print("  Always-on:   ~%s tok   added to every session" % n)
"""


class Repo:
    def __init__(self, tmp):
        self.root = os.path.join(tmp, "repo")
        os.makedirs(os.path.join(self.root, ".claude-plugin"))
        self.plugins = []
        self.claude = os.path.join(tmp, "claude")
        with open(self.claude, "w") as f:
            f.write(FAKE_CLAUDE)
        os.chmod(self.claude, os.stat(self.claude).st_mode | stat.S_IEXEC)
        if os.name == "nt":  # Windows can't start a file by its #! line
            with open(self.claude + ".cmd", "w") as f:
                f.write('@"%s" "%s" %%*\n' % (sys.executable, self.claude))
            self.claude += ".cmd"

    def add(self, name, category, listing, inject=None, exit_code=0, command=None):
        pdir = os.path.join(self.root, "plugins", name)
        os.makedirs(os.path.join(pdir, "hooks"))
        with open(os.path.join(pdir, "listing.txt"), "w") as f:
            f.write("{:,}".format(listing))
        if inject is not None:
            with open(os.path.join(pdir, "hooks", "say.py"), "w") as f:
                f.write("import json, sys\nprint(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', "
                        "'additionalContext': 'x' * %d}}))\n"
                        "sys.stderr.write('note from the hook\\n')\nsys.exit(%d)\n" % (inject, exit_code))
            command = '%s "${CLAUDE_PLUGIN_ROOT}/hooks/say.py"' % sys.executable
        if command is not None:
            hooks = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": command}]}]}}
            with open(os.path.join(pdir, "hooks", "hooks.json"), "w") as f:
                json.dump(hooks, f)
        self.plugins.append({"name": name, "source": "./plugins/" + name, "category": category})
        with open(os.path.join(self.root, ".claude-plugin", "marketplace.json"), "w") as f:
            json.dump({"name": "t", "plugins": self.plugins}, f)
        return pdir

    def run(self, *extra, repo=None, cwd=None):
        return subprocess.run([sys.executable, SCRIPT, "--repo", repo or self.root, "--claude", self.claude] + list(extra),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, cwd=cwd)


class TestAlwaysOn(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_within_budget_passes_and_counts_the_injection(self):
        self.repo.add("s1", "suite", 1000, inject=700)  # 700 chars / 3.5 = 200 tokens
        self.repo.add("lib", "library", 999)
        r = self.repo.run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("| s1 | suite | ~1,000 | ~200 | ~1,200 |", r.stdout)
        self.assertIn("Suite together: **~1,200 tokens**", r.stdout)

    def test_suite_over_budget_fails(self):
        self.repo.add("s1", "suite", 1500)
        self.repo.add("s2", "suite", 400, inject=350)  # 100 tokens: 1,500 + 500 = 2,000, not under 2,000
        r = self.repo.run()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("over budget: suite: ~2000 tokens", r.stdout)

    def test_one_plugin_over_budget_fails_and_is_named(self):
        self.repo.add("s1", "suite", 100)
        self.repo.add("big", "library", 1000)
        r = self.repo.run()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("over budget: big: ~1000 tokens", r.stdout)

    def test_missing_always_on_line_is_could_not_run(self):
        self.repo.add("s1", "suite", 100)
        with open(self.repo.claude, "w") as f:
            f.write("#!/bin/sh\necho nothing here\n")
        r = self.repo.run()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_write_replaces_only_the_marked_block(self):
        self.repo.add("s1", "suite", 100)
        path = os.path.join(self.repo.root, "ALWAYS-ON.md")
        with open(path, "w") as f:
            f.write("intro\n<!-- always-on:begin -->\nold\n<!-- always-on:end -->\noutro\n")
        r = self.repo.run("--write")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(path) as f:
            text = f.read()
        self.assertTrue(text.startswith("intro\n<!-- always-on:begin -->\n| Plugin |"), text)
        self.assertNotIn("old", text)
        self.assertTrue(text.endswith("<!-- always-on:end -->\noutro\n"), text)

    def test_failing_hook_is_could_not_run_not_zero_weight(self):
        # 1,500 listed plus 1,000 injected is over budget. Counted as zero, it reads 1,500 and passes.
        self.repo.add("s1", "suite", 1500, inject=3500, exit_code=1)
        r = self.repo.run()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("s1: SessionStart hook exited 1: note from the hook", r.stderr)
        self.assertNotIn("Suite together", r.stdout)

    def test_hook_command_that_cannot_start_is_could_not_run(self):
        self.repo.add("s1", "suite", 100, command="no-such-program-for-always-on")
        r = self.repo.run()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("s1: SessionStart hook exited", r.stderr)

    def test_hook_that_exits_clean_and_prints_nothing_is_zero_weight(self):
        # bring-loop and kata-harness stay quiet in a project that doesn't use them: they ran, and weigh nothing.
        self.repo.add("s1", "suite", 1000, command='%s -c "pass"' % sys.executable)
        r = self.repo.run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("| s1 | suite | ~1,000 | 0 | ~1,000 |", r.stdout)

    def test_plugin_root_is_filled_in_before_the_shell_sees_it(self):
        # POSIX shells would expand it anyway, so this looks at what the shell is handed, on any platform.
        pdir = self.repo.add("s1", "suite", 100, inject=7)
        ran = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with mock.patch.object(always_on.subprocess, "run", return_value=ran) as run:
            always_on.injection_chars(pdir)
        self.assertEqual(run.call_args[0][0], '%s "%s/hooks/say.py"' % (sys.executable, pdir))

    def test_relative_repo_path_still_reaches_the_hook(self):
        # The hook runs from a temporary project, where a path relative to here finds nothing.
        self.repo.add("s1", "suite", 1000, inject=700)
        r = self.repo.run(repo="repo", cwd=self.tmp.name)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("| s1 | suite | ~1,000 | ~200 | ~1,200 |", r.stdout)


class TestMarketplaceHooks(unittest.TestCase):
    """The marketplace's real SessionStart hooks, through this machine's real shell. No claude needed."""

    @unittest.skipUnless(shutil.which("python3"), "the hooks' own commands call python3")
    def test_every_hook_runs_and_only_dojo_protocol_adds_text(self):
        with open(os.path.join(REPO_ROOT, ".claude-plugin", "marketplace.json"), encoding="utf-8") as f:
            names = [p["name"] for p in json.load(f)["plugins"]]
        chars = {n: always_on.injection_chars(os.path.join(REPO_ROOT, "plugins", n)) for n in names}
        with open(os.path.join(REPO_ROOT, "plugins", "dojo-protocol", "PROTOCOL.md"), encoding="utf-8", newline="") as f:
            rules = f.read()
        self.assertEqual({n: c for n, c in chars.items() if c}, {"dojo-protocol": len(rules)})


if __name__ == "__main__":
    unittest.main()
