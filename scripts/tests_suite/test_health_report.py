"""Tests for health_report.py. Run: python3 -m unittest discover -s tests_suite -t .  (from scripts/)

The fixture sessions in fixtures/health/sessions have answers worked out by hand in fixtures/health/expected.json;
the report must reproduce them, and two runs on the same input must write the same bytes.
"""
from __future__ import annotations

import collections
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

try:
    from . import _helpers as H
except ImportError:  # discovered with tests_suite as the top-level directory
    import _helpers as H

import health_report as HR

REPO = os.path.dirname(H.SCRIPTS)
FIX = os.path.join(H.SCRIPTS, "tests_suite", "fixtures", "health")


def quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args)


def write_session(path, entries):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("".join(json.dumps(e) + "\n" for e in entries))


def bash_turn(cmd, out, ts="2026-10-10T10:00:00Z"):
    return [
        {"type": "user", "message": {"role": "user", "content": "go"}, "timestamp": ts},
        {"type": "assistant", "message": {"role": "assistant", "id": "m1", "content": [
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": cmd}}]}, "timestamp": ts},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": out, "is_error": False}]},
         "toolUseResult": {"stdout": out, "stderr": ""}, "timestamp": ts},
    ]


class TestFixtureAnswers(unittest.TestCase):
    def test_counts_match_the_hand_derived_answers(self):
        report, findings = HR.build([os.path.join(FIX, "sessions")], REPO, doctor=False, accuracy=False)
        with open(os.path.join(FIX, "expected.json")) as fh:
            exp = json.load(fh)
        self.assertEqual(report["counters"], exp["counters"])
        by = dict(collections.Counter(f["detector"] for f in findings))
        self.assertEqual(by, exp["findings_by_detector"])

    def test_a_subagent_transcript_is_not_judged_for_rule_5(self):
        report, findings = HR.build([os.path.join(FIX, "sessions", "proj", "subagents")], REPO, doctor=False,
                                    accuracy=False)
        self.assertEqual(report["counters"]["turns_judged"], 0)
        self.assertEqual(report["counters"]["claims_unbacked"], 0)

    def test_every_rule_is_reported_and_unautomated_ones_say_so(self):
        report, _ = HR.build([os.path.join(FIX, "sessions")], REPO, doctor=False, accuracy=False)
        self.assertEqual([r["rule"] for r in report["rules"]], list(range(1, 11)))
        for r in report["rules"]:
            if r["rule"] == 7:
                self.assertIn("needs_a_reader", r)


class TestReproducible(unittest.TestCase):
    def test_two_runs_write_the_same_bytes(self):
        outs = []
        for _ in range(2):
            d = tempfile.mkdtemp(prefix="hr-")
            self.addCleanup(shutil.rmtree, d, True)
            rc = quiet(HR.main, [os.path.join(FIX, "sessions"), "--no-doctor", "--no-accuracy", "--plugins-root", REPO,
                                 "--out", d])
            self.assertEqual(rc, 0)
            outs.append(d)
        for name in ("health.json", "health.md", "evidence.jsonl"):
            with open(os.path.join(outs[0], name), "rb") as a, open(os.path.join(outs[1], name), "rb") as b:
                self.assertEqual(a.read(), b.read(), name)


class TestInputs(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="hr-in-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_secrets_in_excerpts_are_masked(self):
        token = "ghp_" + "A1b2C3d4" * 5  # built at run time, so scanners stay quiet
        write_session(os.path.join(self.dir, "p", "s.jsonl"),
                      bash_turn("API_KEY=hunter2value git push https://x:%s@example.com/r.git" % token, ""))
        _, findings = HR.build([self.dir], REPO, doctor=False, accuracy=False)
        text = json.dumps(findings)
        self.assertNotIn(token, text)
        self.assertNotIn("hunter2value", text)
        self.assertIn("[masked]", text)

    def test_a_large_whole_file_read_counts(self):
        ts = "2026-10-10T10:00:00Z"
        entries = [
            {"type": "user", "message": {"role": "user", "content": "read it"}, "timestamp": ts},
            {"type": "assistant", "message": {"role": "assistant", "id": "m1", "content": [
                {"type": "tool_use", "id": "r1", "name": "Read", "input": {"file_path": "/w/big.log"}}]}, "timestamp": ts},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "r1", "content": "x" * (HR.BIG_READ_CHARS + 1)}]}, "timestamp": ts},
        ]
        write_session(os.path.join(self.dir, "p", "s.jsonl"), entries)
        report, _ = HR.build([self.dir], REPO, doctor=False, accuracy=False)
        self.assertEqual(report["counters"]["big_reads"], 1)

    def test_a_window_keeps_only_dated_entries_inside_it(self):
        inside = bash_turn("grep -rn TODO src/", "", ts="2026-10-10T10:00:00Z")
        outside = bash_turn("grep -rn FIXME src/", "", ts="2026-10-20T10:00:00Z")
        undated = [{"type": "summary", "summary": "x"}]
        write_session(os.path.join(self.dir, "p", "s.jsonl"), inside + outside + undated)
        report, _ = HR.build([self.dir], REPO, since="2026-10-01", until="2026-10-15", doctor=False, accuracy=False)
        self.assertEqual(report["counters"]["empty_probe"], 1)
        self.assertEqual(report["inputs"]["files"][0]["lines"], 3)

    def test_no_transcripts_is_a_could_not_run(self):
        self.assertEqual(quiet(HR.main, [self.dir, "--no-doctor", "--no-accuracy"]), 2)

    def test_bad_dates_are_refused(self):
        self.assertEqual(quiet(HR.main, [self.dir, "--since", "10/02/2026"]), 2)


if __name__ == "__main__":
    unittest.main()
