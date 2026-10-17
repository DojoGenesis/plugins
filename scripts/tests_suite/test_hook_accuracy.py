"""Tests for hook_accuracy.py. Run: python3 -m unittest discover -s tests_suite -t .  (from scripts/)

The runner is exercised against small fixture trees written here and against stand-in hooks, so these tests do not
depend on what the real hooks currently get right. One test runs the repository's own fixtures twice and requires
identical JSON, the property the health report relies on.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import textwrap
import unittest

try:
    from . import _helpers as H
except ImportError:  # discovered with tests_suite as the top-level directory
    import _helpers as H

import hook_accuracy as HA

REPO = os.path.dirname(H.SCRIPTS)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


class TreeCase(unittest.TestCase):
    """A scratch repository with stand-in hook scripts: their behaviour is fixed here, not by the real hooks."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="ha-test-")
        self.addCleanup(shutil.rmtree, self.root, True)
        # dojo-verify stand-in: blocks when the final message contains BLOCKME
        write(os.path.join(self.root, "plugins/dojo-verify/hooks/stop_evidence.py"), textwrap.dedent('''\
            import json, sys
            p = json.load(sys.stdin)
            if "BLOCKME" in (p.get("last_assistant_message") or ""):
                print(json.dumps({"decision": "block", "reason": "x"}))
            '''))
        # dojo-gates stand-in: a missing-path note when stdout says MISSING
        write(os.path.join(self.root, "plugins/dojo-gates/hooks/bash_after.py"), textwrap.dedent('''\
            import json, sys
            p = json.load(sys.stdin)
            out = (p.get("tool_response") or {}).get("stdout", "") + p.get("error", "")
            if "MISSING" in out:
                ctx = ("dojo-gates: config-first \\u2014 that output looks like a missing path, which usually points "
                       "at configuration rather than code: x.")
                print(json.dumps({"hookSpecificOutput": {"hookEventName": p["hook_event_name"], "additionalContext": ctx}}))
            '''))

    def fixtures(self, plugin, name, data):
        write(os.path.join(self.root, "plugins", plugin, "fixtures", "accuracy", name), json.dumps(data))


class TestWilson(unittest.TestCase):
    def test_known_values(self):
        lo, hi = HA.wilson(10, 10)
        self.assertAlmostEqual(lo, 0.722, places=3)
        self.assertEqual(hi, 1.0)
        lo, hi = HA.wilson(5, 10)
        self.assertAlmostEqual(lo, 0.237, places=3)
        self.assertAlmostEqual(hi, 0.763, places=3)

    def test_no_trials(self):
        self.assertIsNone(HA.wilson(0, 0))


class TestLoading(TreeCase):
    def test_duplicate_ids_are_refused(self):
        self.fixtures("dojo-verify", "a.json", {"hook": "dojo-verify/stop", "cases": [
            {"id": "x", "expect": "fire", "turn": [{"say": "BLOCKME"}]},
            {"id": "x", "expect": "fire", "turn": [{"say": "BLOCKME"}]}]})
        with self.assertRaises(HA.FixtureError):
            HA.load_fixtures(self.root)

    def test_a_case_without_an_id_is_refused(self):
        self.fixtures("dojo-verify", "a.json", {"hook": "dojo-verify/stop", "cases": [{"expect": "fire"}]})
        with self.assertRaises(HA.FixtureError):
            HA.load_fixtures(self.root)

    def test_bad_expectations_are_refused(self):
        self.fixtures("dojo-gates", "a.json", {"hook": "dojo-gates/config-first", "cases": [
            {"id": "x", "expect_kinds": ["paths"], "command": "ls"}]})
        with self.assertRaises(HA.FixtureError):
            HA.evaluate(HA.load_fixtures(self.root), self.root)


class TestScoring(TreeCase):
    def setUp(self):
        super().setUp()
        self.fixtures("dojo-verify", "stop.json", {"hook": "dojo-verify/stop", "cases": [
            {"id": "tp", "expect": "fire", "turn": [{"edit": "/w/a.py"}, {"say": "BLOCKME"}]},
            {"id": "fn", "expect": "fire", "turn": [{"edit": "/w/a.py"}, {"say": "fine"}]},
            {"id": "fp", "expect": "silent", "turn": [{"edit": "/w/a.py"}, {"say": "BLOCKME"}]},
            {"id": "tn", "expect": "silent", "turn": [{"edit": "/w/a.py"}, {"say": "fine"}]},
            {"id": "edge", "expect": "silent", "borderline": True, "turn": [{"say": "BLOCKME"}]},
        ]})
        self.fixtures("dojo-gates", "cf.json", {"hook": "dojo-gates/config-first", "cases": [
            {"id": "path", "expect_kinds": ["path"], "command": "cat x", "stdout": "MISSING"},
            {"id": "none", "expect_kinds": [], "command": "cat y", "stdout": "fine"},
            {"id": "miss", "expect_kinds": [], "known_miss": True, "command": "cat z", "stdout": "MISSING"},
        ]})

    def test_confusion_counts_and_rates(self):
        report = HA.evaluate(HA.load_fixtures(self.root), self.root)
        rows = dict((r["hook"], r) for r in report["rows"])
        v = rows["dojo-verify/stop"]
        self.assertEqual((v["tp"], v["fp"], v["fn"], v["tn"]), (1, 1, 1, 1))
        self.assertEqual((v["borderline"], v["borderline_fired"]), (1, 1))
        self.assertEqual(v["precision"], 0.5)
        self.assertEqual(v["recall"], 0.5)
        p = rows["dojo-gates/config-first:path"]
        self.assertEqual((p["tp"], p["fp"], p["fn"], p["tn"]), (1, 1, 0, 1))  # a known miss still counts
        self.assertEqual(rows["dojo-gates/config-first:auth"]["tn"], 3)

    def test_known_misses_do_not_fail_the_run_but_new_disagreements_do(self):
        report = HA.evaluate(HA.load_fixtures(self.root), self.root)
        new = HA.failures(report)
        known = HA.failures(report, known=True)
        self.assertEqual(sorted(x.split()[1] for x in new), ["fn", "fp"])
        self.assertEqual([x.split()[1] for x in known], ["miss"])

    def test_only_filters_hooks(self):
        report = HA.evaluate(HA.load_fixtures(self.root), self.root, only=["dojo-gates/config-first:path"])
        self.assertEqual([r["hook"] for r in report["rows"]], ["dojo-gates/config-first:path"])

    def test_exit_codes(self):
        empty = tempfile.mkdtemp(prefix="ha-empty-")
        self.addCleanup(shutil.rmtree, empty, True)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(HA.main(["--fixtures", self.root]), 1)
            self.assertEqual(HA.main(["--fixtures", empty]), 2)


class TestRepositoryFixtures(unittest.TestCase):
    def test_two_runs_give_the_same_report(self):
        fixtures = HA.load_fixtures(REPO)
        self.assertGreater(len(fixtures), 50)
        first = json.dumps(HA.evaluate(fixtures, REPO), sort_keys=True)
        second = json.dumps(HA.evaluate(HA.load_fixtures(REPO), REPO), sort_keys=True)
        self.assertEqual(first, second)

    def test_every_case_has_a_source(self):
        for path, case in HA.load_fixtures(REPO):
            self.assertTrue(case.get("source"), "%s: %s has no source" % (path, case["id"]))


if __name__ == "__main__":
    unittest.main()
