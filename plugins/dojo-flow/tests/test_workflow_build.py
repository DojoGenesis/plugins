"""Behaviour tests for workflows/build.js, run under a Node stub harness. The stub checks model and effort on every
subagent call and scripts the answers by label, so every path (refusals, dead subagents, throws) is driven for real."""
import json
import os
import re
import unittest

from wf_helpers import BUILD_JS, CASES, DAG_OPS, needs_node, run_node, run_workflow

GATES = ["npm test", "npm run lint"]
TRACKS = [
    {"name": "api", "prompt": "build the api", "files": ["src/api/"]},
    {"name": "ui", "prompt": "build the ui", "files": ["src/ui/"]},
]
VERIFIED_WORD = re.compile(r"\bVERIFIED\b")
NULL = {"__null": True}


def gate_rows(gates=GATES, **over):
    rows = [{"cmd": g, "ran": True, "exit": 0, "tail": "ok"} for g in gates]
    for i, change in over.items():
        rows[int(i)].update(change)
    return rows


def contract(tracks=TRACKS, coupled=None, **over):
    names = [t["name"] for t in tracks]
    pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            pair = {"pair": [names[i], names[j]], "coupled": False}
            if coupled and set(coupled) == {names[i], names[j]}:
                pair.update({"coupled": True, "sharedContract": "the response shape"})
            pairs.append(pair)
    body = {"proceed": True, "blockers": [], "contractText": "CONTRACT TEXT", "contractWritten": True,
            "baseline": {"isGit": True, "dirtyFiles": ["notes.txt"]}, "tracks": [], "trackIndependence": pairs,
            "trackGuidance": {n: "read first" for n in names}}
    body.update(over)
    return body


def defaults(tracks=TRACKS, gates=GATES, questions=0):
    rules = [
        {"match": "^contract$", "respond": contract(tracks)},
        {"match": "^scout:", "respond": {"plan": "the plan", "filesRead": ["x"],
                                         "questions": [{"briefing": "Q%d" % i} for i in range(questions)]}},
        {"match": "^advise:", "respond": {"advice": "do the thing"}},
    ]
    for t in tracks:
        rules.append({"match": "^build:%s$" % t["name"],
                      "respond": {"complete": True, "filesChanged": [t["files"][0].rstrip("/") + "/index.js"],
                                  "summary": "done", "adviceFollowed": []}})
        rules.append({"match": "^resume:%s$" % t["name"],
                      "respond": {"complete": True, "filesChanged": [t["files"][0].rstrip("/") + "/index.js"],
                                  "summary": "finished", "adviceFollowed": []}})
    rules += [
        {"match": "^integrate$", "respond": {"complete": True, "filesChanged": [], "gates": gate_rows(gates), "summary": "ok"}},
        {"match": "^audit$", "respond": {"proceed": True, "blockers": [], "treeChecked": True, "unownedChanges": [],
                                         "gates": gate_rows(gates), "notes": ""}},
        {"match": "^faithful:audit$", "respond": {"faithful": True, "drift": [], "unsupported": []}},
        {"match": "^accurate:audit$", "respond": {"accurate": True, "errors": []}},
    ]
    return rules


def good_args(**over):
    a = {"goal": "ship the feature", "tracks": TRACKS, "gates": GATES, "repo": "/work/repo"}
    a.update(over)
    return a


class BuildCase(unittest.TestCase):
    def run_build(self, args=None, responses=None, args_raw=None, tracks=TRACKS, gates=GATES, questions=0):
        rules = (responses or []) + defaults(tracks, gates, questions)
        out = run_workflow(BUILD_JS, args if args is not None else good_args(), rules, args_raw=args_raw)
        self.assertIsNone(out["error"], "the script threw: %s" % out["error"])
        self.assertEqual(out["violations"], [], "the stub saw a bad subagent call")
        self.assertIsInstance(out["result"], dict)
        card = out["result"]["scorecard"]
        self.assertIsInstance(card, dict, "every return path must carry a scorecard")
        self.assertEqual(card["dispatched"], len(out["calls"]), "dispatched must equal the calls the stub saw")
        return out

    def labels(self, out):
        return [c["label"] for c in out["calls"]]

    def assert_not_verified(self, out, why=""):
        card = out["result"]["scorecard"]
        self.assertNotEqual(card["verdict"], "VERIFIED", why)
        self.assertIsNone(VERIFIED_WORD.search(card["text"]), "the card says VERIFIED: " + why)
        return card


@needs_node
class HappyPathTests(BuildCase):
    def test_everything_returns_and_the_card_says_verified(self):
        out = self.run_build()
        card = out["result"]["scorecard"]
        self.assertEqual(card["verdict"], "VERIFIED", card["reasons"])
        self.assertEqual(card["reasons"], [])
        self.assertEqual(card["failed"], [])
        self.assertEqual(card["dispatched"], 9)
        self.assertEqual(card["returned"], 9)
        self.assertEqual(len(VERIFIED_WORD.findall(card["text"])), 1)
        self.assertIn("verdict: VERIFIED", card["text"])

    def test_roles_get_the_documented_models_and_efforts(self):
        out = self.run_build()
        by = {}
        for c in out["calls"]:
            by[c["label"]] = (c["model"], c["effort"])
        self.assertEqual(by["contract"], ("opus", "xhigh"))
        self.assertEqual(by["scout:api"], ("haiku", "low"))
        self.assertEqual(by["build:ui"], ("sonnet", "medium"))
        self.assertEqual(by["integrate"], ("sonnet", "medium"))
        self.assertEqual(by["audit"], ("opus", "xhigh"))
        self.assertEqual(by["faithful:audit"], ("sonnet", "medium"))
        self.assertEqual(by["accurate:audit"], ("haiku", "medium"))

    def test_the_script_computes_the_ownership_map_and_reserves_the_contract(self):
        out = self.run_build()
        m = out["result"]["ownershipMap"]
        self.assertEqual(m["api"], ["src/api"])
        self.assertEqual(m["contract"], [".dojo/dag-contract.md"])

    def test_prompts_carry_the_contract_text_inline(self):
        out = self.run_build()
        for c in out["calls"]:
            if c["label"].startswith(("scout:", "build:")):
                self.assertIn("CONTRACT TEXT", c["prompt"], c["label"])
        for c in out["calls"]:
            if c["label"].startswith("build:"):
                self.assertIn("src/", c["prompt"])
                self.assertIn("Do not run git add", c["prompt"])

    def test_args_may_arrive_as_a_json_string(self):
        out = self.run_build(args_raw=json.dumps(good_args()))
        self.assertEqual(out["result"]["scorecard"]["verdict"], "VERIFIED")

    def test_phases_run_in_order(self):
        out = self.run_build()
        self.assertEqual(out["phases"], ["Contract", "Scout", "Integrate", "Audit"])

    def test_model_and_effort_overrides_reach_every_call(self):
        out = self.run_build(good_args(models={"builder": "opus"}, effort="low"))
        for c in out["calls"]:
            self.assertEqual(c["effort"], "low")
            if c["label"].startswith("build:"):
                self.assertEqual(c["model"], "opus")
        out = self.run_build(good_args(effort={"judge": "high"}))
        by = {c["label"]: c["effort"] for c in out["calls"]}
        self.assertEqual(by["contract"], "high")
        self.assertEqual(by["scout:api"], "low")


@needs_node
class VerdictTableTests(BuildCase):
    def check(self, why, responses=None, args=None, reason_has=None, failed_label=None, **kw):
        out = self.run_build(args, responses, **kw)
        card = self.assert_not_verified(out, why)
        self.assertEqual(card["verdict"], "UNVERIFIED", why)
        if reason_has:
            self.assertTrue(any(reason_has in r for r in card["reasons"]), "%s: %r" % (why, card["reasons"]))
        if failed_label:
            self.assertIn(failed_label, [f["label"] for f in card["failed"]], why)
        return out

    def test_a_null_scout(self):
        out = self.check("null scout", [{"match": "^scout:api$", "respond": NULL}], failed_label="scout:api", reason_has="not scouted")
        self.assertNotIn("build:api", self.labels(out))
        self.assertIn("build:ui", self.labels(out))

    def test_a_null_builder(self):
        self.check("null builder", [{"match": "^build:ui$", "respond": NULL}], failed_label="build:ui", reason_has="builder returned nothing")

    def test_a_build_that_is_not_complete(self):
        self.check("complete false", [{"match": "^build:ui$", "respond": {"complete": False, "filesChanged": [], "summary": "half", "adviceFollowed": []}}],
                   reason_has="complete=false")

    def test_no_checks_given_is_unverified_not_vacuously_verified(self):
        for args in (good_args(gates=[]), {k: v for k, v in good_args().items() if k != "gates"}):
            out = self.check("no gates", args=args, gates=[], reason_has="no checks were given")

    def test_the_integrator_says_a_check_did_not_run(self):
        rows = gate_rows(**{"1": {"ran": False}})
        self.check("ran false", [{"match": "^integrate$", "respond": {"complete": True, "filesChanged": [], "gates": rows, "summary": ""}}],
                   reason_has="did not run the check")

    def test_the_integrator_reports_an_easier_command(self):
        rows = gate_rows()
        rows[0]["cmd"] = "true"
        self.check("different cmd", [{"match": "^integrate$", "respond": {"complete": True, "filesChanged": [], "gates": rows, "summary": ""}}],
                   reason_has="did not report the check")

    def test_the_integrator_leaves_a_check_out(self):
        self.check("missing gate", [{"match": "^integrate$", "respond": {"complete": True, "filesChanged": [], "gates": gate_rows()[:1], "summary": ""}}],
                   reason_has="did not report the check")

    def test_a_check_that_exits_nonzero(self):
        rows = gate_rows(**{"0": {"exit": 1}})
        self.check("exit 1", [{"match": "^integrate$", "respond": {"complete": True, "filesChanged": [], "gates": rows, "summary": ""}}],
                   reason_has="check failed")

    def test_the_integrator_passes_but_the_audit_rerun_fails(self):
        rows = gate_rows(**{"1": {"exit": 2}})
        self.check("audit rerun", [{"match": "^audit$", "respond": {"proceed": True, "blockers": [], "treeChecked": True,
                                                                     "unownedChanges": [], "gates": rows}}], reason_has="under the audit")

    def test_the_audit_does_not_approve(self):
        self.check("proceed false", [{"match": "^audit$", "respond": {"proceed": False, "blockers": ["seam"], "treeChecked": True,
                                                                       "unownedChanges": [], "gates": gate_rows()}}], reason_has="did not approve")

    def test_the_audit_approves_but_lists_a_blocker(self):
        self.check("blocker", [{"match": "^audit$", "respond": {"proceed": True, "blockers": ["a seam"], "treeChecked": True,
                                                                 "unownedChanges": [], "gates": gate_rows()}}], reason_has="blocker")

    def test_unowned_changes(self):
        self.check("unowned", [{"match": "^audit$", "respond": {"proceed": True, "blockers": [], "treeChecked": True,
                                                                 "unownedChanges": ["elsewhere.js"], "gates": gate_rows()}}], reason_has="outside the ownership map")

    def test_the_tree_check_did_not_run(self):
        self.check("tree not checked", [{"match": "^audit$", "respond": {"proceed": True, "blockers": [], "treeChecked": False,
                                                                          "unownedChanges": [], "gates": gate_rows()}}], reason_has="tree check did not run")

    def test_not_a_git_repo(self):
        self.check("no git", [{"match": "^contract$", "respond": contract(baseline={"isGit": False, "dirtyFiles": []})}], reason_has="not a git repository")

    def test_a_missing_or_null_baseline_gives_a_scorecard_not_a_throw(self):
        no_baseline = contract()
        del no_baseline["baseline"]
        self.check("baseline omitted", [{"match": "^contract$", "respond": no_baseline}], reason_has="not a git repository")
        self.check("baseline null", [{"match": "^contract$", "respond": contract(baseline=None)}], reason_has="not a git repository")

    def test_two_tracks_named_proto_are_refused_whole_script(self):
        tracks = [{"name": "__proto__", "prompt": "p", "files": ["src/a.js"]}, {"name": "__proto__", "prompt": "p", "files": ["src/a.js"]}]
        out = self.run_build(good_args(tracks=tracks))
        self.assertTrue(out["result"].get("refused"))
        self.assertEqual(out["calls"], [])
        self.assertIn("duplicate track name", out["result"]["reason"])

    def test_a_windows_drive_path_outside_the_repo_is_refused(self):
        tracks = [{"name": "a", "prompt": "p", "files": ["C:\\other\\x"]}, {"name": "b", "prompt": "p", "files": ["src/b.js"]}]
        out = self.run_build(good_args(tracks=tracks))
        self.assertTrue(out["result"].get("refused"))
        self.assertEqual(out["calls"], [])
        self.assertIn("absolute path outside the repo", out["result"]["reason"])

    def test_a_builder_reports_a_file_it_does_not_own(self):
        self.check("outside", [{"match": "^build:api$", "respond": {"complete": True, "filesChanged": ["src/ui/index.js"], "summary": "", "adviceFollowed": []}}],
                   reason_has="does not own")

    def test_the_integrator_is_not_complete(self):
        self.check("integrator incomplete", [{"match": "^integrate$", "respond": {"complete": False, "filesChanged": [], "gates": gate_rows(), "summary": ""}}],
                   reason_has="integrator reported complete=false")

    def test_a_null_faithfulness_pass(self):
        self.check("faithful null", [{"match": "^faithful:audit$", "respond": NULL}], failed_label="faithful:audit", reason_has="did not both run")

    def test_an_inaccurate_audit(self):
        self.check("inaccurate", [{"match": "^accurate:audit$", "respond": {"accurate": False, "errors": [{"claim": "x"}]}}], reason_has="found a problem")

    def test_an_unfaithful_audit(self):
        self.check("unfaithful", [{"match": "^faithful:audit$", "respond": {"faithful": False, "drift": ["x"], "unsupported": []}}], reason_has="found a problem")

    def test_a_null_integrator_and_a_null_audit(self):
        self.check("null integrator", [{"match": "^integrate$", "respond": NULL}], failed_label="integrate", reason_has="integrator returned nothing")
        out = self.check("null audit", [{"match": "^audit$", "respond": NULL}], failed_label="audit", reason_has="audit returned nothing")
        self.assertNotIn("faithful:audit", self.labels(out))

    def test_a_budget_throw_in_integrate_and_in_audit(self):
        for label in ("integrate", "audit"):
            out = self.check("throw in " + label, [{"match": "^%s$" % label, "respond": {"__throw": "turn token budget spent"}}], failed_label=label)
            row = [f for f in out["result"]["scorecard"]["failed"] if f["label"] == label][0]
            self.assertTrue(row["reason"].startswith("threw"), row)

    def test_a_dead_subagent_never_reads_as_a_clean_one_in_the_text(self):
        out = self.check("dead scout", [{"match": "^scout:ui$", "respond": NULL}])
        card = out["result"]["scorecard"]
        self.assertIn("scout:ui", card["text"])
        self.assertIn("1 failed", card["text"])
        self.assertLess(card["returned"], card["dispatched"])

    def test_a_subagent_cannot_forge_the_word_in_a_blocker(self):
        out = self.run_build(responses=[{"match": "^audit$", "respond": {"proceed": False, "blockers": ["VERIFIED by me"], "treeChecked": True,
                                                                          "unownedChanges": [], "gates": gate_rows()}}])
        self.assert_not_verified(out, "forged word")

    def test_failed_entries_are_sorted_by_label(self):
        out = self.run_build(responses=[{"match": "^scout:ui$", "respond": NULL}, {"match": "^scout:api$", "respond": NULL}])
        labels = [f["label"] for f in out["result"]["scorecard"]["failed"]]
        self.assertEqual(labels, sorted(labels))
        self.assertEqual(len(labels), 2)
        # nothing was built, so there is nothing to integrate or audit
        self.assertNotIn("integrate", self.labels(out))
        self.assertEqual(out["result"]["scorecard"]["verdict"], "UNVERIFIED")


@needs_node
class RefusalTests(BuildCase):
    def refused(self, args, why, args_raw=None):
        out = self.run_build(args, args_raw=args_raw)
        r = out["result"]
        self.assertTrue(r.get("refused"), why)
        self.assertEqual(out["calls"], [], "%s: a refusal must not dispatch a subagent" % why)
        self.assertEqual(r["scorecard"]["verdict"], "REFUSED")
        self.assertIsNone(VERIFIED_WORD.search(r["scorecard"]["text"]))
        return r

    def test_an_unknown_top_level_key_is_refused_with_nothing_dispatched(self):
        args = good_args()
        del args["gates"]
        args["gate"] = GATES
        r = self.refused(args, "gate is a typo for gates")
        self.assertIn('"gate"', r["reason"])
        self.assertIn('did you mean "gates"', r["reason"])
        self.assertIn("Allowed keys: goal, tracks, gates, repo, models, effort, adviceCap, maxTracks, contractPath, contractDraft", r["reason"])

    def test_every_misspelled_key_is_named_and_a_removed_key_is_refused(self):
        r = self.refused(good_args(maxTrack=4, deps={"ui": ["api"]}), "two unknown keys")
        self.assertIn('"maxTrack"', r["reason"])
        self.assertIn('"deps"', r["reason"])
        self.assertIn("unknown args keys", r["reason"])

    def test_an_unknown_key_in_a_json_string_is_refused_too(self):
        raw = json.dumps(dict(good_args(), Goals="x"))
        r = self.refused(None, "string args", args_raw=raw)
        self.assertIn('"Goals"', r["reason"])

    def test_every_documented_key_is_accepted(self):
        out = self.run_build(good_args(models={"scout": "haiku"}, effort="medium", adviceCap=2, maxTracks=4,
                                       contractPath=".dojo/c.md", contractDraft="draft"))
        self.assertFalse(out["result"].get("refused"), out["result"].get("reason"))

    def test_overlapping_tracks(self):
        tracks = [{"name": "a", "prompt": "p", "files": ["src/x.js"]}, {"name": "b", "prompt": "p", "files": ["src/"]}]
        r = self.refused(good_args(tracks=tracks), "overlap")
        self.assertIn("overlap", r["reason"])
        self.assertIn("src/x.js", r["reason"])

    def test_the_shared_overlap_table_through_the_whole_script(self):
        with open(CASES, encoding="utf-8") as fh:
            cases = json.load(fh)
        for c in cases:
            tracks = [dict(t, prompt="p") for t in c["tracks"]]
            args = {"goal": "g", "tracks": tracks, "gates": ["t"], "repo": c.get("repo", "")}
            if not args["repo"]:
                del args["repo"]
            if c.get("reserved"):
                args["contractPath"] = c["reserved"]
            out = run_workflow(BUILD_JS, args, defaults() + [{"match": ".*", "respond": NULL}])
            self.assertIsNone(out["error"], c["name"])
            refused_at_args = bool(out["result"].get("refused")) and out["calls"] == []
            if c["expect"] == "refuse":
                self.assertTrue(refused_at_args, "%s should be refused before any call" % c["name"])
            else:
                self.assertFalse(refused_at_args, "%s should pass the ownership check" % c["name"])

    def test_the_js_check_and_the_python_check_agree_on_every_case(self):
        with open(CASES, encoding="utf-8") as fh:
            cases = json.load(fh)
        js = run_node("block", BUILD_JS, cases)
        for c, got in zip(cases, js):
            self.assertEqual(got["ok"], c["expect"] == "ok", "%s: %r" % (c["name"], got))

    def test_too_many_tracks(self):
        tracks = [{"name": "t%d" % i, "prompt": "p", "files": ["f%d.js" % i]} for i in range(9)]
        r = self.refused(good_args(tracks=tracks), "9 tracks")
        self.assertIn("maxTracks", r["reason"])

    def test_max_tracks_can_be_raised_and_is_bounded(self):
        tracks = [{"name": "t%d" % i, "prompt": "p", "files": ["f%d.js" % i]} for i in range(9)]
        out = run_workflow(BUILD_JS, good_args(tracks=tracks, maxTracks=9), [{"match": "^contract$", "respond": NULL}])
        self.assertTrue(out["result"]["refused"])
        self.assertIn("contract subagent returned nothing", out["result"]["reason"])
        self.refused(good_args(maxTracks=17), "maxTracks 17")

    def test_bad_roles_models_and_efforts(self):
        self.assertIn("buidler", self.refused(good_args(models={"buidler": "sonnet"}), "typo role")["reason"])
        self.assertIn("builder", self.refused(good_args(models={"builder": "gpt"}), "bad alias")["reason"])
        self.assertIn("effort", self.refused(good_args(effort="extreme"), "bad effort")["reason"])
        self.assertIn("bulder", self.refused(good_args(effort={"bulder": "low"}), "typo effort role")["reason"])
        self.refused(good_args(models=["sonnet"]), "models as a list")

    def test_bad_advice_cap(self):
        self.refused(good_args(adviceCap=7), "7")
        self.refused(good_args(adviceCap="3"), "'3'")
        self.refused(good_args(adviceCap=-1), "-1")

    def test_unparseable_args_and_missing_goal(self):
        self.refused(None, "garbage", args_raw="{not json")
        self.refused(None, "list", args_raw=[1, 2])
        self.refused(good_args(goal=""), "empty goal")
        self.refused({"tracks": TRACKS}, "no goal")

    def test_bad_gates_and_paths(self):
        self.refused(good_args(gates=["a", "a"]), "duplicate gates")
        self.refused(good_args(gates=[1]), "non-string gate")
        self.refused(good_args(contractPath="../escape.md"), "contract path with ..")
        self.refused(good_args(contractPath="C:/elsewhere/c.md", repo=None), "absolute contract path with no repo")
        self.refused(good_args(contractPath="/elsewhere/c.md", repo=None), "absolute posix contract path with no repo")
        self.refused(good_args(contractPath="/work/repo/src/api/c.md"), "contract path inside a track's directory")
        self.refused(good_args(tracks=[{"name": "a", "files": ["a.js"]}]), "track with no prompt")

    def test_a_scorecard_comes_back_even_for_a_refusal(self):
        r = self.refused(good_args(adviceCap=99), "cap")
        self.assertEqual(r["scorecard"]["dispatched"], 0)
        self.assertEqual(r["scorecard"]["returned"], 0)


@needs_node
class ContractGateTests(BuildCase):
    def test_a_coupled_pair_stops_the_run_before_any_scout(self):
        out = self.run_build(responses=[{"match": "^contract$", "respond": contract(coupled=["api", "ui"])}])
        r = out["result"]
        self.assertTrue(r["refused"])
        self.assertIn("coupled", r["reason"])
        self.assertIn("the response shape", r["reason"])
        self.assertEqual(self.labels(out), ["contract"])
        self.assert_not_verified(out)

    def test_an_uncertified_pair_stops_the_run(self):
        out = self.run_build(responses=[{"match": "^contract$", "respond": contract(trackIndependence=[])}])
        self.assertTrue(out["result"]["refused"])
        self.assertIn("not certified", out["result"]["reason"])
        self.assertEqual(self.labels(out), ["contract"])

    def test_a_non_boolean_coupled_flag_counts_as_coupled(self):
        bad = contract()
        bad["trackIndependence"][0]["coupled"] = "no"
        out = self.run_build(responses=[{"match": "^contract$", "respond": bad}])
        self.assertTrue(out["result"]["refused"])
        self.assertEqual(self.labels(out), ["contract"])

    def test_a_null_contract_is_a_refusal_with_the_failure_in_the_card(self):
        out = self.run_build(responses=[{"match": "^contract$", "respond": NULL}])
        card = out["result"]["scorecard"]
        self.assertTrue(out["result"]["refused"])
        self.assertEqual([f["label"] for f in card["failed"]], ["contract"])
        self.assertEqual((card["dispatched"], card["returned"]), (1, 0))
        self.assert_not_verified(out)

    def test_a_throwing_contract_is_a_refusal_not_a_crash(self):
        out = self.run_build(responses=[{"match": "^contract$", "respond": {"__throw": "turn token budget spent"}}])
        card = out["result"]["scorecard"]
        self.assertTrue(out["result"]["refused"])
        self.assertTrue(card["failed"][0]["reason"].startswith("threw"))
        self.assert_not_verified(out)

    def test_proceed_false_and_an_unwritten_contract_both_refuse(self):
        out = self.run_build(responses=[{"match": "^contract$", "respond": contract(proceed=False, blockers=["a file already exists there"])}])
        self.assertIn("already exists", out["result"]["reason"])
        out = self.run_build(responses=[{"match": "^contract$", "respond": contract(contractWritten=False)}])
        self.assertIn("not written", out["result"]["reason"])
        out = self.run_build(responses=[{"match": "^contract$", "respond": contract(contractText="  ")}])
        self.assertTrue(out["result"]["refused"])
        self.assertEqual(self.labels(out), ["contract"])

    def test_without_tracks_the_run_stops_after_the_contract_with_a_plan(self):
        proposed = [{"name": "api", "prompt": "p", "files": ["src/api/"]}, {"name": "ui", "prompt": "p", "files": ["src/ui/"]}]
        args = {"goal": "ship it", "gates": GATES}
        out = self.run_build(args, [{"match": "^contract$", "respond": dict(contract(), tracks=proposed, contractWritten=False, trackIndependence=[])}])
        r = out["result"]
        self.assertTrue(r["planOnly"])
        self.assertEqual(self.labels(out), ["contract"])
        self.assertEqual(r["plan"]["tracks"], proposed)
        self.assertEqual(r["plan"]["problems"], [])
        self.assertEqual(r["scorecard"]["verdict"], "PLAN ONLY")
        self.assertIn("contract", out["calls"][0]["prompt"].lower())
        self.assertIn("Write NOTHING", out["calls"][0]["prompt"])
        self.assert_not_verified(out)

    def test_a_plan_that_overlaps_reports_its_problems(self):
        proposed = [{"name": "a", "prompt": "p", "files": ["x.js"]}, {"name": "b", "prompt": "p", "files": ["x.js"]}]
        out = self.run_build({"goal": "g"}, [{"match": "^contract$", "respond": dict(contract(), tracks=proposed, contractWritten=False, trackIndependence=[])}])
        self.assertTrue(any("overlap" in p for p in out["result"]["plan"]["problems"]))

    def test_the_contract_prompt_names_the_path_and_the_no_overwrite_rule(self):
        out = self.run_build()
        p = out["calls"][0]["prompt"]
        self.assertIn(".dojo/dag-contract.md", p)
        self.assertIn("already exists", p)
        out = self.run_build(good_args(contractPath="/scratch/contract.md"))
        self.assertIn("/scratch/contract.md", out["calls"][0]["prompt"])
        self.assertNotIn("contract", out["result"]["ownershipMap"])
        out = self.run_build(good_args(contractPath="C:/scratch/contract.md"))
        self.assertIn("C:/scratch/contract.md", out["calls"][0]["prompt"])
        self.assertNotIn("contract", out["result"]["ownershipMap"])


@needs_node
class AdviceAndStuckTests(BuildCase):
    def test_questions_beyond_the_cap_are_dropped_and_logged(self):
        out = self.run_build(questions=5)
        advise = [l for l in self.labels(out) if l.startswith("advise:")]
        self.assertEqual(len(advise), 6)  # 3 per track, 2 tracks
        self.assertTrue(any("dropped" in l and "adviceCap is 3" in l for l in out["logs"]), out["logs"])
        t = out["result"]["tracks"][0]
        self.assertEqual(t["droppedQuestions"], 2)

    def test_advice_cap_zero_asks_nobody(self):
        out = self.run_build(good_args(adviceCap=0), questions=2)
        self.assertEqual([l for l in self.labels(out) if l.startswith("advise:")], [])

    def test_advice_is_recorded_by_the_script_and_reaches_the_builder(self):
        out = self.run_build(questions=1)
        ledger = out["result"]["adviceLedger"]
        self.assertEqual(len(ledger), 2)
        self.assertTrue(all(e["advice"] == "do the thing" and not e["failed"] for e in ledger))
        build = [c for c in out["calls"] if c["label"] == "build:api"][0]
        self.assertIn("do the thing", build["prompt"])

    def test_a_failed_advisor_is_a_failed_call_and_the_builder_is_told(self):
        out = self.run_build(responses=[{"match": "^advise:api:pre1$", "respond": NULL}], questions=1)
        self.assert_not_verified(out)
        self.assertIn("advise:api:pre1", [f["label"] for f in out["result"]["scorecard"]["failed"]])
        build = [c for c in out["calls"] if c["label"] == "build:api"][0]
        self.assertIn("THE ADVISOR CALL FAILED", build["prompt"])

    def test_stuck_then_one_consult_and_one_resume(self):
        stuck = {"complete": False, "filesChanged": ["src/api/a.js"], "summary": "blocked", "adviceFollowed": [], "stuckQuestion": "which way?"}
        out = self.run_build(responses=[{"match": "^build:api$", "times": 1, "respond": stuck}])
        labels = self.labels(out)
        self.assertIn("advise:api:stuck1", labels)
        self.assertEqual(labels.count("resume:api"), 1)
        self.assertEqual(labels.count("build:api"), 1)
        self.assertEqual(out["result"]["scorecard"]["verdict"], "VERIFIED")

    def test_a_first_attempt_write_outside_ownership_is_not_hidden_by_a_clean_resume(self):
        stuck = {"complete": False, "filesChanged": ["src/api/a.js", "src/ui/hijack.js"], "summary": "blocked",
                 "adviceFollowed": [], "stuckQuestion": "which way?"}
        clean = {"complete": True, "filesChanged": ["src/api/a.js"], "summary": "finished", "adviceFollowed": []}
        out = self.run_build(responses=[{"match": "^build:api$", "times": 1, "respond": stuck},
                                        {"match": "^resume:api$", "respond": clean}])
        card = self.assert_not_verified(out, "first attempt wrote another track's file")
        self.assertTrue(any("api reported changing files it does not own: src/ui/hijack.js" in r for r in card["reasons"]), card["reasons"])
        api = [t for t in out["result"]["tracks"] if t["name"] == "api"][0]
        self.assertEqual(api["outsideOwned"], ["src/ui/hijack.js"])
        self.assertEqual(sorted(api["filesChanged"]), ["src/api/a.js", "src/ui/hijack.js"])
        integ = [c for c in out["calls"] if c["label"] == "integrate"][0]["prompt"]
        self.assertIn("src/ui/hijack.js", integ)

    def test_a_non_string_filesChanged_entry_is_flagged_not_dropped(self):
        for bad in ({"path": "src/ui/x.js"}, 7, None):
            built = {"complete": True, "filesChanged": ["src/api/a.js", bad], "summary": "done", "adviceFollowed": []}
            out = self.run_build(responses=[{"match": "^build:api$", "respond": built}])
            card = self.assert_not_verified(out, "non-string entry %r" % (bad,))
            self.assertTrue(any("api reported changing files it does not own" in r for r in card["reasons"]), card["reasons"])

    def test_a_filesChanged_that_is_not_a_list_cannot_be_verified(self):
        for bad in ("src/ui/x.js", {"a": 1}, 5):
            built = {"complete": True, "filesChanged": bad, "summary": "done", "adviceFollowed": []}
            out = self.run_build(responses=[{"match": "^build:api$", "respond": built}])
            card = self.assert_not_verified(out, "filesChanged %r" % (bad,))
            self.assertTrue(any("api returned a malformed filesChanged" in r for r in card["reasons"]), card["reasons"])

    def test_a_resume_that_repeats_files_does_not_list_them_twice(self):
        stuck = {"complete": False, "filesChanged": ["src/api/a.js"], "summary": "blocked", "adviceFollowed": [], "stuckQuestion": "q?"}
        clean = {"complete": True, "filesChanged": ["src/api/a.js", "src/api/b.js"], "summary": "finished", "adviceFollowed": []}
        out = self.run_build(responses=[{"match": "^build:api$", "times": 1, "respond": stuck},
                                        {"match": "^resume:api$", "respond": clean}])
        api = [t for t in out["result"]["tracks"] if t["name"] == "api"][0]
        self.assertEqual(api["filesChanged"], ["src/api/a.js", "src/api/b.js"])
        self.assertEqual(out["result"]["scorecard"]["verdict"], "VERIFIED", out["result"]["scorecard"]["reasons"])

    def test_a_resume_that_is_still_stuck_is_not_resumed_twice(self):
        stuck = {"complete": False, "filesChanged": [], "summary": "blocked", "adviceFollowed": [], "stuckQuestion": "which way?"}
        out = self.run_build(responses=[{"match": "^(build|resume):api$", "respond": stuck}])
        labels = self.labels(out)
        self.assertEqual(labels.count("resume:api"), 1)
        self.assertEqual(sum(1 for l in labels if l.startswith("advise:api:stuck")), 1)
        self.assert_not_verified(out)

    def test_no_stuck_consult_when_the_cap_is_used_up(self):
        stuck = {"complete": False, "filesChanged": [], "summary": "blocked", "adviceFollowed": [], "stuckQuestion": "?"}
        out = self.run_build(good_args(adviceCap=0), responses=[{"match": "^build:api$", "respond": stuck}])
        self.assertNotIn("resume:api", self.labels(out))


@needs_node
class PromptSafetyTests(BuildCase):
    def test_no_prompt_asks_a_subagent_to_commit_or_push(self):
        out = self.run_build(questions=1)
        for c in out["calls"]:
            self.assertNotRegex(c["prompt"].lower(), r"run git (commit|push)(?! )", c["label"])

    def test_scouts_are_told_to_write_nothing(self):
        out = self.run_build()
        for c in out["calls"]:
            if c["label"].startswith("scout:"):
                self.assertIn("Write nothing", c["prompt"])

    def test_the_integrator_and_audit_prompts_carry_the_checks_verbatim(self):
        out = self.run_build()
        for c in out["calls"]:
            if c["label"] in ("integrate", "audit"):
                for g in GATES:
                    self.assertIn("- " + g, c["prompt"])

    def test_the_audit_prompt_carries_the_baseline_and_the_map(self):
        out = self.run_build()
        p = [c for c in out["calls"] if c["label"] == "audit"][0]["prompt"]
        self.assertIn("notes.txt", p)
        self.assertIn("src/api/", p)
        self.assertIn(".dojo/dag-contract.md", p)


if __name__ == "__main__":
    unittest.main()
