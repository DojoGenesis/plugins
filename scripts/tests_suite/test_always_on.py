"""Tests for scripts/always_on.py, with a stand-in claude binary so no real CLI is needed."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "always_on.py")

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

    def add(self, name, category, listing, inject=None):
        pdir = os.path.join(self.root, "plugins", name)
        os.makedirs(os.path.join(pdir, "hooks"))
        with open(os.path.join(pdir, "listing.txt"), "w") as f:
            f.write("{:,}".format(listing))
        if inject is not None:
            with open(os.path.join(pdir, "hooks", "say.py"), "w") as f:
                f.write("import json\nprint(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', "
                        "'additionalContext': 'x' * %d}}))\n" % inject)
            hooks = {"hooks": {"SessionStart": [{"hooks": [
                {"type": "command", "command": '%s "${CLAUDE_PLUGIN_ROOT}/hooks/say.py"' % sys.executable}]}]}}
            with open(os.path.join(pdir, "hooks", "hooks.json"), "w") as f:
                json.dump(hooks, f)
        self.plugins.append({"name": name, "source": "./plugins/" + name, "category": category})
        with open(os.path.join(self.root, ".claude-plugin", "marketplace.json"), "w") as f:
            json.dump({"name": "t", "plugins": self.plugins}, f)

    def run(self, *extra):
        return subprocess.run([sys.executable, SCRIPT, "--repo", self.root, "--claude", self.claude] + list(extra),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


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


if __name__ == "__main__":
    unittest.main()
