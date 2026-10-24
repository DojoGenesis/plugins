#!/usr/bin/env python3
"""Turn the held-out author's tasks into `claude plugin eval` cases (PREREG-2026-10-23-routing.md).

    build_cases.py <author-out-dir> <repo-root>

For each task folder in <author-out-dir> (case.json, scaffold.sh, hidden/, reference/):
- the author's files are copied unchanged to evals/routing-2026-10-23/cases/<name>/ (hidden tests and the
  reference stay there, outside every plugin directory, so no agent sandbox ever holds them);
- `hr-*` tasks become plugins/dojo-router/evals/<name>/{case.yaml, scaffold.sh};
- `hf-*` tasks become plugins/dojo-flow/evals/<name>-routed/ and <name>-allopus/, identical except the models map.

The prompts are the author's (hr) or the evaluator's fixed wrapper around the author's args (hf). The graders are
the evaluator's, fixed by the pre-registration. Never overwrites an existing case folder.
"""
import json
import os
import shutil
import sys

HERE = "evals/routing-2026-10-23"

HEADER = (
    "# Held-out case for the pre-registered routing eval (evals/routing-2026-10-23/PREREG-2026-10-23-routing.md).\n"
    "# The task was written by an independent model author from held-out-brief.md, without access to this\n"
    "# repository; its hidden tests live in evals/routing-2026-10-23/cases/, never in the sandbox. The graders\n"
    "# are the evaluator's, fixed by the pre-registration. JSON is valid YAML. Runs spend money: never run\n"
    "# without a cap and a yes.\n"
)

ROUTED = {"scout": "haiku", "builder": "sonnet", "integrator": "sonnet", "reviewer": "sonnet",
          "checker": "haiku", "judge": "opus"}
ALL_OPUS = {k: "opus" for k in ROUTED}

HF_WRAPPER = (
    "Run the dojo-flow build workflow on this repository with exactly the arguments below. Call the Workflow "
    "tool with name \"dojo-flow:build\"; if that name is not known, call it with scriptPath set to the plugin's "
    "workflows/build.js. Set repo to the absolute path of the current directory (run pwd to get it). Do not "
    "change the goal, tracks, gates or models, and do not edit any file yourself. Wait for the workflow to "
    "finish, then reply with its scorecard exactly as returned.\n\nargs (add repo yourself):\n"
)


def judge(task):
    return {
        "type": "llm",
        "name": "quality-judge",
        "focus": "files",
        "criteria": (
            "You are grading the final state of a small Python project after a coding task. Read the project's "
            "files. A correct finish: " + task["expected_outcome"].strip() + " Decide whether the code now does "
            "what that sentence describes, judging behaviour, not style or comments. PASS if it does. FAIL if it "
            "does not, or only partly does."
        ),
    }


def hr_case(task):
    return {
        "schema_version": "1.0",
        "name": task["name"],
        "description": task["description"],
        "tags": ["held-out", "routing", task["kind"]],
        "runs": 6,
        "context": {"scaffold_script": "scaffold.sh", "add_dirs": []},
        "execution": {
            "prompt": task["prompt"],
            "max_turns": 16,
            "timeout_seconds": 900,
            "model": "opus",
            "allowed_tools": ["Read", "Edit", "Write", "Bash", "Glob", "Grep", "Agent", "Skill"],
        },
        "graders": [
            judge(task),
            {"type": "tool_used", "name": "dispatched", "tool": "Agent", "min": 1},
            {"type": "regex", "name": "hook-warned", "target": "trace",
             "pattern": "dojo-router: this .* dispatch names no model", "arm": "with-only"},
        ],
        "expected_outcome": task["expected_outcome"],
    }


def hf_case(task, arm):
    args = {"goal": task["goal"], "tracks": task["tracks"], "gates": task["gates"],
            "models": ROUTED if arm == "routed" else ALL_OPUS}
    return {
        "schema_version": "1.0",
        "name": task["name"] + "-" + arm,
        "description": task["description"] + " (" + ("routed: workflow defaults" if arm == "routed" else "every role on opus") + ")",
        "tags": ["held-out", "routing", task["kind"], arm],
        "runs": 5,
        "context": {"scaffold_script": "scaffold.sh", "add_dirs": []},
        "execution": {
            "prompt": HF_WRAPPER + json.dumps(args, indent=2),
            "max_turns": 12,
            "timeout_seconds": 1800,
            "model": "opus",
            "allowed_tools": ["Read", "Edit", "Write", "Glob", "Grep", "Bash", "Skill", "Workflow"],
        },
        "graders": [
            judge(task),
            {"type": "tool_used", "name": "workflow-ran", "tool": "Workflow", "min": 1},
            {"type": "regex", "name": "scorecard-relayed", "target": "last_message",
             "pattern": "verdict: (VERIFIED|UNVERIFIED|REFUSED|PLAN ONLY)"},
        ],
        "expected_outcome": task["expected_outcome"],
    }


def write_case(folder, case, scaffold):
    os.makedirs(folder)  # refuses an existing folder
    with open(os.path.join(folder, "case.yaml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(HEADER + json.dumps(case, indent=2, ensure_ascii=False) + "\n")
    shutil.copyfile(scaffold, os.path.join(folder, "scaffold.sh"))


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    src, repo = argv[1], argv[2]
    for name in sorted(os.listdir(src)):
        tdir = os.path.join(src, name)
        if not os.path.isfile(os.path.join(tdir, "case.json")):
            continue
        with open(os.path.join(tdir, "case.json"), encoding="utf-8") as f:
            task = json.load(f)
        assert task["name"] == name, "case.json name %r != folder %r" % (task["name"], name)
        shutil.copytree(tdir, os.path.join(repo, HERE, "cases", name))
        scaffold = os.path.join(tdir, "scaffold.sh")
        if name.startswith("hr-"):
            write_case(os.path.join(repo, "plugins", "dojo-router", "evals", name), hr_case(task), scaffold)
        elif name.startswith("hf-"):
            for arm in ("routed", "allopus"):
                write_case(os.path.join(repo, "plugins", "dojo-flow", "evals", name + "-" + arm), hf_case(task, arm), scaffold)
        else:
            print("skipped %s: not hr- or hf-" % name, file=sys.stderr)
            continue
        print("built %s (%s)" % (name, task["kind"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
