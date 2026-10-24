#!/usr/bin/env python3
"""Apply section 4 of PREREG-2026-10-23-routing.md to a finished main run. Standard library only.

    analyze.py R <eval.json> <files-judge.jsonl> [--careful hr-limiter-starve]
    analyze.py F <eval.json> <files-judge.jsonl> [--careful hf-semver-ranges]

Reads the eval's own JSON (per-run cost, judge cost, error, trace path), runs the hidden tests on each kept work
directory (grade_hidden.py), reads the files judge's verdicts (judge_files.py, one JSON line per run), and counts
the model of every subagent and workflow agent from the kept transcripts. Prints the per-cell table, the pooled
figures and what the rule outputs, and writes the same as JSON next to the eval JSON (<eval>-analysis.json).

Arms: in R the eval's `with` arm is routed and `without` is all-opus. In F every case runs in one arm and the arm
is the case name's suffix (`-routed` / `-allopus`); the task is the name without it.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grade_hidden  # noqa: E402
import stats  # noqa: E402

NON_OPUS = ("haiku", "sonnet")


def agent_models(root):
    """Model of each subagent / workflow agent transcript under the kept config dir: list of model ids."""
    out = []
    for path in sorted(glob.glob(os.path.join(root, "config", "projects", "**", "*.jsonl"), recursive=True)):
        if os.sep + "subagents" + os.sep not in path and "/subagents/" not in path:
            continue
        seen = None
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                m = (e.get("message") or {}).get("model")
                if e.get("type") == "assistant" and m and m != "<synthetic>":
                    seen = m
                    break
        if seen:
            out.append(seen)
    return out


def load_runs(study, eval_json, judge_jsonl):
    d = json.load(open(eval_json, encoding="utf-8"))
    verdicts = {}
    if os.path.exists(judge_jsonl):
        for line in open(judge_jsonl, encoding="utf-8"):
            j = json.loads(line)
            verdicts[(j["case"], j["arm"], j["run"])] = j
    rows = []
    for c in d["cases"]:
        for eval_arm, runs in c["arms"].items():
            for i, r in enumerate(runs):
                name = c["name"]
                if study == "R":
                    task, arm = name, ("routed" if eval_arm == "with" else "allopus")
                else:
                    task, arm = name.rsplit("-", 1)
                root = os.path.dirname(os.path.dirname(r["tracePath"])) if r.get("tracePath") else ""
                work = os.path.join(root, "home", "cwd")
                hidden, detail = grade_hidden.run_hidden(os.path.join(HERE, "cases", task), work)
                j = verdicts.get((name, eval_arm, i + 1), {})
                no_output = bool(r.get("error")) and not r.get("turns")
                rows.append({
                    "case": name, "task": task, "arm": arm, "run": i + 1,
                    "cost": r["costUsd"], "judge_cost_in_eval": r.get("judgeCostUsd") or 0.0,
                    "agent_cost": r["costUsd"] - (r.get("judgeCostUsd") or 0.0),
                    "turns": r.get("turns"), "duration_s": r.get("durationSeconds"), "error": r.get("error"),
                    "hidden": hidden, "hidden_detail": detail,
                    "judge": j.get("verdict", "MISSING"), "judge_votes": j.get("votes"), "judge_cost": j.get("cost_usd", 0.0),
                    "agents": agent_models(root) if root else [],
                    "counts": (not no_output) and hidden in ("PASS", "FAIL"),
                })
    return d, rows


def analyze(study, eval_json, judge_jsonl, careful):
    d, rows = load_runs(study, eval_json, judge_jsonl)
    counted = [r for r in rows if r["counts"]]
    tasks = sorted({r["task"] for r in rows})
    cells = {}
    for t in tasks:
        for a in ("routed", "allopus"):
            rs = [r for r in counted if r["task"] == t and r["arm"] == a]
            allrs = [r for r in rows if r["task"] == t and r["arm"] == a]
            cells[(t, a)] = {
                "planned_or_seen": len(allrs), "counted": len(rs),
                "mean_agent_cost": (sum(r["agent_cost"] for r in rs) / len(rs)) if rs else None,
                "hidden_pass": sum(r["hidden"] == "PASS" for r in rs),
                "judge_pass": sum(r["judge"] == "PASS" for r in rs),
                "mean_turns": (sum(r["turns"] or 0 for r in rs) / len(rs)) if rs else None,
                "agents": sum(len(r["agents"]) for r in rs),
                "agents_non_opus": sum(sum(1 for m in r["agents"] if any(k in m for k in NON_OPUS)) for r in rs),
                "models": sorted({m for r in rs for m in r["agents"]}),
            }
    # Cost: every task, careful included.
    cost = {a: {t: [r["agent_cost"] for r in counted if r["task"] == t and r["arm"] == a] for t in tasks} for a in ("routed", "allopus")}
    rho = stats.bootstrap_ratio(cost["routed"], cost["allopus"]) if all(any(v) for v in cost["routed"].values()) and all(any(v) for v in cost["allopus"].values()) else None
    # Quality: standard tasks in R; both tasks in F.
    qtasks = [t for t in tasks if (t != careful or study == "F")]
    def rate(arm, key):
        rs = [r for r in counted if r["task"] in qtasks and r["arm"] == arm]
        return sum(r[key] == "PASS" for r in rs), len(rs)
    xq1, nq1 = rate("routed", "hidden"); xq0, nq0 = rate("allopus", "hidden")
    xj1, nj1 = rate("routed", "judge"); xj0, nj0 = rate("allopus", "judge")
    dq = stats.newcombe_diff(xq1, nq1, xq0, nq0) if nq1 and nq0 else None
    dj = (xj1 / nj1 - xj0 / nj0) if nj1 and nj0 else None
    # Careful case.
    cr, ca = cells.get((careful, "routed")), cells.get((careful, "allopus"))
    harm = (ca["hidden_pass"] - cr["hidden_pass"] >= 2) if cr and ca else None
    careful_win = (cr["hidden_pass"] - ca["hidden_pass"] >= 2) if cr and ca else None
    # Manipulation.
    ag_r = sum(c["agents"] for (t, a), c in cells.items() if a == "routed")
    no_r = sum(c["agents_non_opus"] for (t, a), c in cells.items() if a == "routed")
    ag_o = sum(c["agents"] for (t, a), c in cells.items() if a == "allopus")
    no_o = sum(c["agents_non_opus"] for (t, a), c in cells.items() if a == "allopus")
    if ag_r and ag_o:
        share_r, share_o = no_r / ag_r, no_o / ag_o
        took_effect = share_r >= 0.5 and share_r - share_o >= 0.25
        manip = "took effect" if took_effect else "did not take effect"
    else:
        share_r = share_o = None
        manip = "not measured"
        took_effect = (study == "F")  # the F script sets each agent's model from the map itself
    # Rule.
    if rho is None:
        cost_out = "not computable"
    elif rho[2] < 1:
        cost_out = "savings detected"
    elif rho[1] > 1:
        cost_out = "increase detected"
    else:
        cost_out = "no detectable difference"
    if dq is None or dj is None:
        q_out = "not computable"
    elif dq[2] < 0 and dj <= 0:
        q_out = "loss detected"
    elif dq[1] >= -0.15 and dj >= -0.15:
        q_out = "non-inferior"
    else:
        q_out = "not resolved"
    q_gain = bool(dq and dj is not None and dq[1] > 0 and dj >= 0)
    if cost_out == "savings detected":
        verdict = {"non-inferior": "saves, no measured loss", "not resolved": "saves, quality not resolved",
                   "loss detected": "saves at a quality cost"}.get(q_out, "saves, quality not computable")
    elif cost_out == "increase detected":
        verdict = "costs more"
    else:
        verdict = "no detectable difference in cost"
    planned = {a: sum(1 for r in rows if r["arm"] == a) for a in ("routed", "allopus")}
    n_counted = {a: sum(1 for r in counted if r["arm"] == a) for a in ("routed", "allopus")}
    reasons = []
    if any(n_counted[a] * 2 < planned[a] for a in planned):
        reasons.append("fewer than half of the planned runs counted in an arm")
    if cost_out != "savings detected" and (manip == "did not take effect" or (manip == "not measured" and study == "R")):
        reasons.append("no savings detected and routing did not take effect or was not measured")
    if reasons:
        verdict = "inconclusive: " + "; ".join(reasons)
    if harm:
        verdict += " (careful-case harm flagged)"
    return {
        "study": study, "eval_json": os.path.basename(eval_json), "claude_version": d.get("claudeVersion"),
        "started_at": d.get("startedAt"), "eval_cost_usd": d.get("costUsd"), "partial": d.get("partial"),
        "cells": {"%s|%s" % k: v for k, v in cells.items()},
        "runs_planned_or_seen": planned, "runs_counted": n_counted,
        "missing": [{k: r[k] for k in ("case", "arm", "run", "error", "hidden", "hidden_detail")} for r in rows if not r["counts"]],
        "pooled_mean_agent_cost": {a: (stats.pooled_mean({t: v for t, v in cost[a].items() if v}) if any(cost[a].values()) else None) for a in cost},
        "cost_ratio": rho, "cost_outcome": cost_out,
        "quality_tasks": qtasks, "hidden": {"routed": [xq1, nq1], "allopus": [xq0, nq0], "dq_newcombe": dq},
        "judge": {"routed": [xj1, nj1], "allopus": [xj0, nj0], "dj": dj},
        "quality_outcome": q_out, "quality_gain_unexpected": q_gain,
        "careful": careful, "careful_harm": harm, "careful_routed_wins_by_2": careful_win,
        "agents_non_opus": {"routed": [no_r, ag_r], "allopus": [no_o, ag_o], "share_routed": share_r, "share_allopus": share_o},
        "manipulation": manip, "verdict": verdict,
        "runs": rows,
    }


def main(argv):
    if len(argv) < 4 or argv[1] not in ("R", "F"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    study, eval_json, judge_jsonl = argv[1], argv[2], argv[3]
    careful = argv[argv.index("--careful") + 1] if "--careful" in argv else ("hr-limiter-starve" if study == "R" else "hf-semver-ranges")
    res = analyze(study, eval_json, judge_jsonl, careful)
    out = os.path.splitext(eval_json)[0] + "-analysis.json"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, indent=1)
    print("study %s  claude %s  eval cost $%.4f  partial %s" % (study, res["claude_version"], res["eval_cost_usd"], res["partial"]))
    print("task | arm | counted/seen | mean agent cost | hidden pass | judge pass | mean turns | non-opus agents | models")
    for k, c in sorted(res["cells"].items()):
        t, a = k.split("|")
        mc = "—" if c["mean_agent_cost"] is None else "$%.3f" % c["mean_agent_cost"]
        mt = "—" if c["mean_turns"] is None else "%.1f" % c["mean_turns"]
        print("%s | %s | %d/%d | %s | %d | %d | %s | %d/%d | %s" % (t, a, c["counted"], c["planned_or_seen"], mc, c["hidden_pass"], c["judge_pass"], mt, c["agents_non_opus"], c["agents"], ",".join(c["models"])))
    print("pooled mean agent cost:", res["pooled_mean_agent_cost"])
    print("cost ratio routed/all-opus (point, 95% lo, hi):", res["cost_ratio"], "->", res["cost_outcome"])
    print("hidden:", res["hidden"], "| judge:", res["judge"], "->", res["quality_outcome"], "| unexpected gain:", res["quality_gain_unexpected"])
    print("careful %s: harm %s, routed wins by 2+: %s" % (res["careful"], res["careful_harm"], res["careful_routed_wins_by_2"]))
    print("non-opus agents:", res["agents_non_opus"], "->", res["manipulation"])
    print("missing runs:", len(res["missing"]))
    print("VERDICT:", res["verdict"])
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
