"""Behaviour tests for workflows/converge.js under the Node stub harness: majority vote, caps, severity, the fix
gate, and the verdict table."""
import re
import unittest

from wf_helpers import CONVERGE_JS, needs_node, run_workflow

GATES = ["npm test"]
NULL = {"__null": True}
VERIFIED_WORD = re.compile(r"\bVERIFIED\b")
LENSES = [{"name": "L", "prompt": "look for bugs"}]


def finding(claim="a bug", severity="high", files=None, **kw):
    f = {"claim": claim, "evidence": "foo.js:3", "severity": severity, "fix": "change it"}
    if files is not None:
        f["files"] = files
    f.update(kw)
    return f


def rows(gates=GATES, **over):
    out = [{"cmd": g, "ran": True, "exit": 0, "tail": "ok"} for g in gates]
    for i, change in over.items():
        out[int(i)].update(change)
    return out


def votes(lens, index, results):
    """Rules for the three verifiers of one finding. results: list of True (refute), False (confirm), None, or a raw dict."""
    rules = []
    for k, r in enumerate(results):
        if r is None:
            body = NULL
        elif isinstance(r, dict):
            body = r
        else:
            body = {"refuted": r}
        rules.append({"match": "^verify:%s:%d:%d$" % (lens, index, k + 1), "respond": body})
    return rules


def lens_report(findings, summary="done"):
    return {"findings": findings, "summary": summary}


def defaults(reports, gates=GATES):
    rules = []
    for name, rep in reports.items():
        rules.append({"match": "^audit:%s$" % name, "respond": rep})
    rules += [
        {"match": "^verify:", "respond": {"refuted": False}},
        {"match": "^baseline$", "respond": {"isGit": True, "dirtyFiles": ["notes.txt"]}},
        {"match": "^fix:", "respond": {"complete": True, "filesChanged": ["a.js"], "summary": "fixed", "deviations": []}},
        {"match": "^gate:run$", "respond": {"gates": rows(gates), "summary": ""}},
        {"match": "^gate:accept$", "respond": {"proceed": True, "blockers": [], "treeChecked": True, "unownedChanges": [], "gates": rows(gates)}},
        {"match": "^faithful:accept$", "respond": {"faithful": True, "drift": [], "unsupported": []}},
        {"match": "^accurate:accept$", "respond": {"accurate": True, "errors": []}},
    ]
    return rules


class ConvergeCase(unittest.TestCase):
    def run_c(self, args, reports=None, responses=None, gates=GATES, args_raw=None):
        reports = reports if reports is not None else {"L": lens_report([finding()])}
        out = run_workflow(CONVERGE_JS, args, (responses or []) + defaults(reports, gates), args_raw=args_raw)
        self.assertIsNone(out["error"], "the script threw: %s" % out["error"])
        self.assertEqual(out["violations"], [], "the stub saw a bad subagent call")
        card = out["result"]["scorecard"]
        self.assertIsInstance(card, dict)
        self.assertEqual(card["dispatched"], len(out["calls"]))
        return out

    def labels(self, out):
        return [c["label"] for c in out["calls"]]

    def status_of(self, out, claim=None):
        fs = out["result"]["findings"]
        if claim:
            fs = [f for f in fs if f["claim"] == claim]
        return fs[0]["status"]


@needs_node
class MajorityTests(ConvergeCase):
    def vote(self, results, **extra):
        return self.run_c({"lenses": LENSES}, responses=votes("L", 1, results), **extra)

    def test_two_refutes_kill_the_finding(self):
        out = self.vote([True, True, False])
        self.assertEqual(self.status_of(out), "refuted")
        self.assertEqual(out["result"]["counts"]["refuted"], 1)
        self.assertEqual(len([l for l in self.labels(out) if l.startswith("verify:")]), 3)

    def test_a_refuted_finding_stays_in_the_result(self):
        out = self.vote([True, True, True])
        self.assertEqual(len(out["result"]["findings"]), 1)
        self.assertEqual(out["result"]["findings"][0]["votes"], {"refute": 3, "confirm": 0, "none": 0})

    def test_one_refute_and_two_nulls_is_unresolved_and_kept(self):
        out = self.vote([True, None, None])
        self.assertEqual(self.status_of(out), "unresolved")
        failed = [f["label"] for f in out["result"]["scorecard"]["failed"]]
        self.assertEqual(sorted(failed), ["verify:L:1:2", "verify:L:1:3"])
        self.assertEqual(out["result"]["scorecard"]["verdict"], "UNVERIFIED")

    def test_two_confirms_and_a_null_confirm(self):
        out = self.vote([False, False, None])
        self.assertEqual(self.status_of(out), "confirmed")
        self.assertEqual(len(out["result"]["scorecard"]["failed"]), 1)

    def test_one_refute_one_confirm_one_null_is_unresolved(self):
        self.assertEqual(self.status_of(self.vote([True, False, None])), "unresolved")

    def test_three_nulls_are_unresolved_with_three_failures(self):
        out = self.vote([None, None, None])
        self.assertEqual(self.status_of(out), "unresolved")
        self.assertEqual(len(out["result"]["scorecard"]["failed"]), 3)

    def test_a_non_boolean_verdict_counts_as_null(self):
        out = self.vote([{"refuted": "yes"}, {"refuted": "yes"}, False])
        self.assertEqual(self.status_of(out), "unresolved")
        reasons = [f["reason"] for f in out["result"]["scorecard"]["failed"]]
        self.assertEqual(len(reasons), 2)
        self.assertTrue(all("malformed verdict" in r for r in reasons))

    def test_verifiers_run_on_opus_at_the_judge_effort(self):
        out = self.vote([False, False, False])
        for c in out["calls"]:
            if c["label"].startswith("verify:"):
                self.assertEqual((c["model"], c["effort"]), ("opus", "xhigh"))
            if c["label"].startswith("audit:"):
                self.assertEqual((c["model"], c["effort"]), ("sonnet", "medium"))


@needs_node
class SeverityAndCapTests(ConvergeCase):
    def test_upper_case_severity_is_normalised_not_malformed(self):
        out = self.run_c({"lenses": LENSES}, {"L": lens_report([finding(severity="HIGH")])})
        f = out["result"]["findings"][0]
        self.assertEqual(f["severity"], "high")
        self.assertFalse(f["severityMalformed"])
        self.assertEqual(out["result"]["counts"]["malformedSeverity"], 0)
        self.assertEqual(len([l for l in self.labels(out) if l.startswith("verify:")]), 3)

    def test_an_unknown_severity_is_logged_and_still_verified(self):
        out = self.run_c({"lenses": LENSES}, {"L": lens_report([finding(severity="urgent")])})
        f = out["result"]["findings"][0]
        self.assertTrue(f["severityMalformed"])
        self.assertEqual(f["severityGiven"], "urgent")
        self.assertEqual(out["result"]["counts"]["malformedSeverity"], 1)
        self.assertTrue(any("urgent" in l and "outside" in l for l in out["logs"]), out["logs"])
        self.assertEqual(len([l for l in self.labels(out) if l.startswith("verify:")]), 3)

    def test_null_and_claimless_findings_get_no_verifiers(self):
        out = self.run_c({"lenses": LENSES}, {"L": lens_report([finding(), None, "text", {"severity": "high"}, {"claim": "  ", "severity": "high"}])})
        verify = [l for l in self.labels(out) if l.startswith("verify:")]
        self.assertEqual(verify, ["verify:L:1:1", "verify:L:1:2", "verify:L:1:3"])
        self.assertEqual(len(out["result"]["findings"]), 1)
        self.assertEqual(out["result"]["counts"]["malformedFinding"], 4)
        self.assertEqual(sum(1 for l in out["logs"] if "is not an object with a claim" in l), 4)

    def test_a_lens_whose_findings_are_all_malformed_is_a_dead_lens_not_a_clean_one(self):
        for bad in ([None, None, None], [{"severity": "high"}, "text"]):
            out = self.run_c({"lenses": LENSES}, {"L": lens_report(bad)})
            card = out["result"]["scorecard"]
            self.assertEqual(card["verdict"], "UNVERIFIED", card["reasons"])
            self.assertIn("malformed report", card["failed"][0]["reason"])
            self.assertIn("lenses with no usable report: L", card["text"])
            self.assertEqual(out["result"]["findings"], [])

    def test_a_lens_with_some_malformed_findings_cannot_end_reviewed(self):
        out = self.run_c({"lenses": LENSES}, {"L": lens_report([finding(), None])})
        card = out["result"]["scorecard"]
        self.assertEqual(card["verdict"], "UNVERIFIED", card["reasons"])
        self.assertTrue(any("lens L sent 1 finding(s)" in r for r in card["reasons"]), card["reasons"])
        self.assertEqual(len(out["result"]["findings"]), 1)

    def test_a_fix_run_with_a_malformed_finding_cannot_end_verified(self):
        out = self.run_c({"lenses": LENSES, "fix": True, "gates": GATES},
                         {"L": lens_report([finding(files=["a.js"]), None])})
        card = out["result"]["scorecard"]
        self.assertNotEqual(card["verdict"], "VERIFIED")
        self.assertTrue(any("lens L sent 1 finding(s)" in r for r in card["reasons"]), card["reasons"])

    def test_the_schema_carries_the_severity_enum(self):
        out = self.run_c({"lenses": LENSES})
        self.assertEqual(out["violations"], [])
        with open(CONVERGE_JS, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("enum: ['critical', 'high', 'medium', 'low']", src)

    def test_seven_high_findings_with_a_cap_of_five(self):
        fs = [finding(claim="bug %d" % i) for i in range(7)]
        out = self.run_c({"lenses": LENSES}, {"L": lens_report(fs)})
        dropped = out["result"]["droppedByCap"]
        self.assertEqual(len(dropped), 2)
        self.assertEqual([d["lens"] for d in dropped], ["L", "L"])
        self.assertEqual(len([l for l in self.labels(out) if l.startswith("verify:")]), 15)
        self.assertTrue(any("cap is 5" in l and "bug 5" in l for l in out["logs"]), out["logs"])
        self.assertEqual(out["result"]["counts"]["droppedByCap"], 2)
        statuses = [f["status"] for f in out["result"]["findings"]]
        self.assertEqual(statuses.count("not verified (dropped by topPerLens cap)"), 2)

    def test_critical_findings_are_verified_before_high_ones_under_the_cap(self):
        fs = [finding(claim="h%d" % i) for i in range(3)] + [finding(claim="c0", severity="critical")]
        out = self.run_c({"lenses": LENSES, "topPerLens": 2}, {"L": lens_report(fs)})
        by = {f["claim"]: f["status"] for f in out["result"]["findings"]}
        self.assertEqual(by["c0"], "confirmed")
        self.assertEqual(by["h0"], "confirmed")
        self.assertEqual(by["h1"], "not verified (dropped by topPerLens cap)")

    def test_medium_and_low_are_reported_as_below_threshold(self):
        fs = [finding(claim="m", severity="medium"), finding(claim="l", severity="low")]
        out = self.run_c({"lenses": LENSES}, {"L": lens_report(fs)})
        self.assertEqual([f["status"] for f in out["result"]["findings"]], ["not verified (below threshold)"] * 2)
        self.assertEqual([l for l in self.labels(out) if l.startswith("verify:")], [])
        self.assertEqual(out["result"]["counts"]["belowThreshold"], 2)


@needs_node
class AuditOnlyTests(ConvergeCase):
    def test_audit_only_says_reviewed_and_never_verified(self):
        out = self.run_c({"lenses": LENSES})
        card = out["result"]["scorecard"]
        self.assertEqual(card["verdict"], "REVIEWED")
        self.assertIn("audit only, nothing changed", card["text"])
        self.assertIsNone(VERIFIED_WORD.search(card["text"]))
        self.assertEqual(out["result"]["mode"], "audit-only")
        labels = self.labels(out)
        self.assertFalse(any(l.startswith(("fix:", "gate:", "baseline")) for l in labels))
        self.assertEqual(out["phases"], ["Audit"])

    def test_even_with_gates_and_confirmed_findings_nothing_changes_by_default(self):
        out = self.run_c({"lenses": LENSES, "gates": GATES})
        self.assertEqual(out["result"]["scorecard"]["verdict"], "REVIEWED")
        self.assertFalse(any(l.startswith(("fix:", "gate:")) for l in self.labels(out)))

    def test_a_dead_lens_is_not_a_clean_lens(self):
        lenses = [{"name": "L", "prompt": "p"}, {"name": "M", "prompt": "p"}]
        out = self.run_c({"lenses": lenses}, {"L": lens_report([]), "M": lens_report([])}, responses=[{"match": "^audit:M$", "respond": NULL}])
        card = out["result"]["scorecard"]
        self.assertEqual(card["verdict"], "UNVERIFIED")
        self.assertIsNone(VERIFIED_WORD.search(card["text"]))
        self.assertEqual([f["label"] for f in card["failed"]], ["audit:M"])
        self.assertEqual((card["dispatched"], card["returned"]), (2, 1))
        self.assertIn("lenses with no usable report: M", card["text"])

    def test_a_throwing_lens_is_a_failed_lens(self):
        out = self.run_c({"lenses": LENSES}, responses=[{"match": "^audit:L$", "respond": {"__throw": "boom"}}])
        card = out["result"]["scorecard"]
        self.assertEqual(card["verdict"], "UNVERIFIED")
        self.assertTrue(card["failed"][0]["reason"].startswith("threw"))

    def test_a_malformed_report_is_counted_as_failed(self):
        out = self.run_c({"lenses": LENSES}, {"L": {"findings": "none", "summary": "x"}})
        card = out["result"]["scorecard"]
        self.assertEqual(card["verdict"], "UNVERIFIED")
        self.assertIn("malformed report", card["failed"][0]["reason"])
        self.assertEqual(card["returned"], 0)

    def test_no_findings_is_a_clean_review(self):
        out = self.run_c({"lenses": LENSES}, {"L": lens_report([])})
        self.assertEqual(out["result"]["scorecard"]["verdict"], "REVIEWED")
        self.assertEqual(out["result"]["findings"], [])

    def test_args_as_a_json_string(self):
        out = self.run_c(None, args_raw='{"lenses": [{"name": "L", "prompt": "p"}]}')
        self.assertEqual(out["result"]["scorecard"]["verdict"], "REVIEWED")


@needs_node
class RefusalTests(ConvergeCase):
    def refused(self, args, why, args_raw=None):
        out = self.run_c(args, args_raw=args_raw)
        r = out["result"]
        self.assertTrue(r.get("refused"), why)
        self.assertEqual(out["calls"], [], why)
        self.assertEqual(r["scorecard"]["verdict"], "REFUSED")
        self.assertEqual(r["droppedByCap"], [])
        return r

    def test_lenses_are_required(self):
        self.refused({}, "none")
        self.refused({"lenses": []}, "empty")
        self.refused({"lenses": [{"name": "a"}]}, "no prompt")
        self.refused({"lenses": [{"name": "a", "prompt": "p"}, {"name": "A", "prompt": "q"}]}, "duplicate")
        self.refused({"lenses": [{"name": "__proto__", "prompt": "p"}, {"name": "__proto__", "prompt": "q"}]}, "duplicate proto")
        self.refused({"lenses": [{"name": "l%d" % i, "prompt": "p"} for i in range(11)]}, "too many")

    def test_fix_without_gates_is_refused(self):
        r = self.refused({"lenses": LENSES, "fix": True}, "no gates")
        self.assertIn("gates", r["reason"])
        self.refused({"lenses": LENSES, "fix": True, "gates": []}, "empty gates")

    def test_bad_options(self):
        self.refused({"lenses": LENSES, "topPerLens": 0}, "cap 0")
        self.refused({"lenses": LENSES, "topPerLens": 21}, "cap 21")
        self.refused({"lenses": LENSES, "models": {"lenz": "sonnet"}}, "unknown role")
        self.refused({"lenses": LENSES, "models": {"lens": "gpt"}}, "bad alias")
        self.refused({"lenses": LENSES, "effort": "extreme"}, "bad effort")
        self.refused({"lenses": LENSES, "gates": ["a", "a"]}, "duplicate gate")
        self.refused(None, "garbage", args_raw="not json")

    def test_an_unknown_top_level_key_is_refused_with_nothing_dispatched(self):
        r = self.refused({"lenses": LENSES, "fixx": True, "gate": GATES}, "typos")
        self.assertIn('"fixx"', r["reason"])
        self.assertIn('did you mean "fix"', r["reason"])
        self.assertIn('"gate"', r["reason"])
        self.assertIn('did you mean "gates"', r["reason"])
        self.assertIn("Allowed keys: lenses, gates, fix, fixTracks, repo, topPerLens, models, effort", r["reason"])

    def test_every_documented_key_is_accepted(self):
        out = self.run_c({"lenses": LENSES, "gates": GATES, "fix": False, "fixTracks": [], "repo": "/work/repo",
                          "topPerLens": 2, "models": {"lens": "sonnet"}, "effort": "medium"})
        self.assertFalse(out["result"].get("refused"), out["result"].get("reason"))

    def test_overlapping_given_fix_tracks_are_refused_before_any_call(self):
        tracks = [{"name": "a", "prompt": "p", "files": ["src/"]}, {"name": "b", "prompt": "p", "files": ["src/x.js"]}]
        r = self.refused({"lenses": LENSES, "fix": True, "gates": GATES, "fixTracks": tracks}, "overlap")
        self.assertIn("overlap", r["reason"])


@needs_node
class FixPathTests(ConvergeCase):
    ARGS = {"lenses": LENSES, "fix": True, "gates": GATES}

    def with_files(self, files=None):
        return {"L": lens_report([finding(files=files if files is not None else ["a.js"])])}

    def test_a_clean_fix_run_is_verified(self):
        out = self.run_c(self.ARGS, self.with_files())
        card = out["result"]["scorecard"]
        self.assertEqual(card["verdict"], "VERIFIED", card["reasons"])
        self.assertEqual(len(VERIFIED_WORD.findall(card["text"])), 1)
        labels = self.labels(out)
        for want in ("baseline", "fix:fix-1", "gate:run", "gate:accept", "faithful:accept", "accurate:accept"):
            self.assertIn(want, labels)
        self.assertEqual(out["phases"], ["Audit", "Fix", "Gate"])
        by = {c["label"]: c["model"] for c in out["calls"]}
        self.assertEqual((by["fix:fix-1"], by["gate:run"], by["gate:accept"], by["baseline"]), ("sonnet", "sonnet", "opus", "haiku"))

    def test_fix_as_a_string_runs_nothing(self):
        out = self.run_c({"lenses": LENSES, "fix": "true", "gates": GATES}, self.with_files())
        self.assertEqual(out["result"]["scorecard"]["verdict"], "REVIEWED")
        self.assertFalse(any(l.startswith(("fix:", "gate:", "baseline")) for l in self.labels(out)))
        self.assertTrue(any("boolean true" in l for l in out["logs"]))

    def test_only_confirmed_findings_are_fixed(self):
        out = self.run_c(self.ARGS, self.with_files(), responses=votes("L", 1, [True, True, False]))
        self.assertEqual(out["result"]["scorecard"]["verdict"], "REVIEWED")
        self.assertFalse(any(l.startswith("fix:") for l in self.labels(out)))

    def test_findings_that_share_files_land_in_one_track_and_others_stay_apart(self):
        fs = [finding(claim="one", files=["a", "b"]), finding(claim="two", files=["b", "c"]), finding(claim="three", files=["d"])]
        out = self.run_c(self.ARGS, {"L": lens_report(fs)}, responses=[
            {"match": "^fix:fix-1$", "respond": {"complete": True, "filesChanged": ["a", "b", "c"], "summary": "", "deviations": []}},
            {"match": "^fix:fix-2$", "respond": {"complete": True, "filesChanged": ["d"], "summary": "", "deviations": []}}])
        tracks = out["result"]["fixTracks"]
        self.assertEqual([t["files"] for t in tracks], [["a", "b", "c"], ["d"]])
        self.assertEqual([t["findings"] for t in tracks], [[0, 1], [2]])
        self.assertEqual(out["result"]["scorecard"]["verdict"], "VERIFIED", out["result"]["scorecard"]["reasons"])

    def test_a_directory_and_a_file_inside_it_join_one_track(self):
        fs = [finding(claim="one", files=["src/"]), finding(claim="two", files=["src/x.js"])]
        out = self.run_c(self.ARGS, {"L": lens_report(fs)}, responses=[
            {"match": "^fix:", "respond": {"complete": True, "filesChanged": ["src/x.js"], "summary": "", "deviations": []}}])
        self.assertEqual(len(out["result"]["fixTracks"]), 1)

    def test_a_finding_with_no_files_is_not_auto_fixable_and_blocks_the_verdict(self):
        fs = [finding(claim="has files", files=["a.js"]), finding(claim="no files", files=[])]
        out = self.run_c(self.ARGS, {"L": lens_report(fs)})
        self.assertEqual([n["claim"] for n in out["result"]["notAutoFixable"]], ["no files"])
        card = out["result"]["scorecard"]
        self.assertEqual(card["verdict"], "UNVERIFIED")
        self.assertTrue(any("no usable files" in r for r in card["reasons"]))

    def test_only_unfixable_findings_means_no_fix_phase_and_no_pass(self):
        out = self.run_c(self.ARGS, {"L": lens_report([finding(files=[])])})
        card = out["result"]["scorecard"]
        self.assertEqual(card["verdict"], "UNVERIFIED")
        self.assertFalse(any(l.startswith(("fix:", "baseline", "gate:")) for l in self.labels(out)))

    def test_given_fix_tracks_are_used(self):
        tracks = [{"name": "mine", "prompt": "fix it", "files": ["a.js"]}]
        out = self.run_c(dict(self.ARGS, fixTracks=tracks), self.with_files())
        self.assertIn("fix:mine", self.labels(out))
        self.assertEqual(out["result"]["scorecard"]["verdict"], "VERIFIED")

    def test_given_fix_tracks_that_do_not_cover_a_confirmed_finding_are_unverified(self):
        tracks = [{"name": "mine", "prompt": "fix it", "files": ["b.js"]}]
        out = self.run_c(dict(self.ARGS, fixTracks=tracks), self.with_files(["a.js"]),
                         responses=[{"match": "^fix:", "respond": {"complete": True, "filesChanged": ["b.js"], "summary": ""}}])
        card = out["result"]["scorecard"]
        self.assertEqual(card["verdict"], "UNVERIFIED", card["reasons"])
        self.assertIsNone(VERIFIED_WORD.search(card["text"]))
        self.assertTrue(any("not fixed" in r for r in card["reasons"]), card["reasons"])
        self.assertEqual([n["claim"] for n in out["result"]["notAutoFixable"]], ["a bug"])
        self.assertFalse(any(l.startswith("fix:") for l in self.labels(out)))

    def test_each_given_fix_track_gets_only_the_findings_inside_its_files(self):
        fs = [finding(claim="in a", files=["a.js"]), finding(claim="in b", files=["src/b.js"])]
        tracks = [{"name": "ta", "prompt": "fix a", "files": ["a.js"]}, {"name": "tb", "prompt": "fix b", "files": ["src/"]},
                  {"name": "tc", "prompt": "fix c", "files": ["c.js"]}]
        out = self.run_c(dict(self.ARGS, fixTracks=tracks), {"L": lens_report(fs)}, responses=[
            {"match": "^fix:ta$", "respond": {"complete": True, "filesChanged": ["a.js"], "summary": ""}},
            {"match": "^fix:tb$", "respond": {"complete": True, "filesChanged": ["src/b.js"], "summary": ""}}])
        prompts = {c["label"]: c["prompt"] for c in out["calls"] if c["label"].startswith("fix:")}
        self.assertEqual(sorted(prompts), ["fix:ta", "fix:tb"])  # tc owns no finding file, so it is not dispatched
        self.assertIn("in a", prompts["fix:ta"])
        self.assertNotIn("in b", prompts["fix:ta"])
        self.assertIn("in b", prompts["fix:tb"])
        self.assertNotIn("in a", prompts["fix:tb"])
        self.assertEqual(out["result"]["scorecard"]["verdict"], "VERIFIED", out["result"]["scorecard"]["reasons"])

    def test_fix_tracks_without_fix_true_are_ignored_and_logged(self):
        tracks = [{"name": "mine", "prompt": "fix it", "files": ["a.js"]}]
        out = self.run_c({"lenses": LENSES, "fixTracks": tracks}, self.with_files())
        self.assertEqual(out["result"]["scorecard"]["verdict"], "REVIEWED")
        self.assertTrue(any("fixTracks was given but fix is not true" in l for l in out["logs"]), out["logs"])

    def check_unverified(self, why, responses, reason_has):
        out = self.run_c(self.ARGS, self.with_files(), responses=responses)
        card = out["result"]["scorecard"]
        self.assertEqual(card["verdict"], "UNVERIFIED", why)
        self.assertIsNone(VERIFIED_WORD.search(card["text"]), why)
        self.assertTrue(any(reason_has in r for r in card["reasons"]), "%s: %r" % (why, card["reasons"]))
        return out

    def test_the_verdict_table(self):
        accept = {"proceed": True, "blockers": [], "treeChecked": True, "unownedChanges": [], "gates": rows()}
        self.check_unverified("fixer null", [{"match": "^fix:", "respond": NULL}], "returned nothing")
        self.check_unverified("fixer incomplete", [{"match": "^fix:", "respond": {"complete": False, "filesChanged": [], "summary": ""}}], "complete=false")
        self.check_unverified("fixer outside files", [{"match": "^fix:", "respond": {"complete": True, "filesChanged": ["other.js"], "summary": ""}}], "does not own")
        self.check_unverified("gate run null", [{"match": "^gate:run$", "respond": NULL}], "gate run returned nothing")
        self.check_unverified("gate run not run", [{"match": "^gate:run$", "respond": {"gates": rows(**{"0": {"ran": False}}), "summary": ""}}], "did not run")
        self.check_unverified("gate run easier command", [{"match": "^gate:run$", "respond": {"gates": [{"cmd": "true", "ran": True, "exit": 0}], "summary": ""}}], "did not report")
        self.check_unverified("gate run failed", [{"match": "^gate:run$", "respond": {"gates": rows(**{"0": {"exit": 1}}), "summary": ""}}], "check failed")
        self.check_unverified("accept null", [{"match": "^gate:accept$", "respond": NULL}], "acceptance gate returned nothing")
        self.check_unverified("accept rerun fails", [{"match": "^gate:accept$", "respond": dict(accept, gates=rows(**{"0": {"exit": 3}}))}], "under the acceptance gate")
        self.check_unverified("accept says no", [{"match": "^gate:accept$", "respond": dict(accept, proceed=False)}], "did not approve")
        self.check_unverified("accept blocker", [{"match": "^gate:accept$", "respond": dict(accept, blockers=["x"])}], "blocker")
        self.check_unverified("tree not checked", [{"match": "^gate:accept$", "respond": dict(accept, treeChecked=False)}], "tree check did not run")
        self.check_unverified("unowned", [{"match": "^gate:accept$", "respond": dict(accept, unownedChanges=["z.js"])}], "outside the fix ownership map")
        self.check_unverified("not git", [{"match": "^baseline$", "respond": {"isGit": False, "dirtyFiles": []}}], "no git repository")
        self.check_unverified("baseline null", [{"match": "^baseline$", "respond": NULL}], "baseline")
        self.check_unverified("faithful null", [{"match": "^faithful:accept$", "respond": NULL}], "did not both run")
        self.check_unverified("accurate no", [{"match": "^accurate:accept$", "respond": {"accurate": False, "errors": [{"claim": "x"}]}}], "found a problem")
        self.check_unverified("accept throws", [{"match": "^gate:accept$", "respond": {"__throw": "turn token budget spent"}}], "acceptance gate returned nothing")

    def test_an_unresolved_finding_blocks_a_verified_fix(self):
        fs = [finding(claim="sure", files=["a.js"]), finding(claim="unsure", files=["b.js"])]
        out = self.run_c(self.ARGS, {"L": lens_report(fs)}, responses=votes("L", 2, [True, None, None]) + [
            {"match": "^fix:", "respond": {"complete": True, "filesChanged": ["a.js"], "summary": ""}}])
        card = out["result"]["scorecard"]
        self.assertEqual(card["verdict"], "UNVERIFIED")
        self.assertTrue(any("unresolved" in r for r in card["reasons"]))


if __name__ == "__main__":
    unittest.main()
