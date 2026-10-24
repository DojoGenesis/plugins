#!/usr/bin/env python3
"""The `quality-judge` reference, run after the eval (PREREG-2026-10-23-routing.md, amendment 1).

On this Windows machine the eval's `focus: files` view reaches the judge empty ("(no file changes)") even when the
agent changed files, so the in-eval judge can't see anything. This runs the same grader outside the eval: the same
criteria string (read from the case.yaml), the same judge (Opus), three votes with the majority deciding, and the
same view, files only and never the trace. The files are the run's changes against a fresh scaffold: every added or
modified text file in full, plus the names of deleted ones.

    judge_files.py <case.yaml> <scaffold.sh> <work-dir>
        Prints one JSON line: {"verdict": "PASS"|"FAIL"|"COULD NOT RUN", "votes": [...], "cost_usd": ...}.

Each vote is `claude -p --model opus` on the logged-in account (the session's claude.ai login; this script
never reads or sets an API key) with no tools, no setting sources, no MCP servers and no slash commands, so no
user hook, plugin or memory reaches the judge.
"""
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

VOTES = 3
SKIP_DIRS = {".git", "__pycache__"}
MAX_FILE = 20000
MAX_TOTAL = 80000
SYSTEM = (
    "You are an evaluation judge. You are shown the files a coding agent added or changed in a small project, "
    "and a grading criterion. Apply the criterion to the files only. End your reply with one line that is exactly "
    "VERDICT: PASS or VERDICT: FAIL."
)


def criteria_of(case_yaml):
    text = open(case_yaml, encoding="utf-8").read()
    body = text[text.index("{"):]  # the case files are JSON after a comment header
    case = json.loads(body)
    return [g for g in case["graders"] if g["name"] == "quality-judge"][0]["criteria"]


def tree(root):
    out = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            full = os.path.join(dp, fn)
            out[os.path.relpath(full, root).replace(os.sep, "/")] = full
    return out


def changes(scaffold, work):
    with tempfile.TemporaryDirectory(prefix="routing-judge-", ignore_cleanup_errors=True) as tmp:
        base = os.path.join(tmp, "base")
        os.makedirs(base)
        bash = shutil.which("bash") or "bash"
        subprocess.run([bash, os.path.abspath(scaffold)], cwd=base, capture_output=True, text=True, timeout=120, check=True)
        before, after = tree(base), tree(work)
        added = sorted(p for p in after if p not in before)
        modified = sorted(p for p in after if p in before and not filecmp.cmp(before[p], after[p], shallow=False))
        deleted = sorted(p for p in before if p not in after)
    parts, total = [], 0
    for label, paths in (("added", added), ("modified", modified)):
        for p in paths:
            try:
                body = open(after[p], encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                body = "(not a text file)"
            if len(body) > MAX_FILE:
                body = body[:MAX_FILE] + "\n... (cut at %d characters)" % MAX_FILE
            chunk = "=== %s: %s ===\n%s\n" % (label, p, body)
            if total + len(chunk) > MAX_TOTAL:
                parts.append("=== %s: %s === (not shown: the shown files already reach %d characters)\n" % (label, p, MAX_TOTAL))
                continue
            parts.append(chunk)
            total += len(chunk)
    for p in deleted:
        parts.append("=== deleted: %s ===\n" % p)
    return "".join(parts)


def vote(prompt, cwd):
    # The prompt goes in on stdin: a Windows command line stops at about 32K characters.
    cmd = ["claude", "-p", "--model", "opus", "--system-prompt", SYSTEM, "--tools", "",
           "--setting-sources", "project", "--strict-mcp-config", "--disable-slash-commands",
           "--no-session-persistence", "--max-turns", "1", "--output-format", "json"]
    p = subprocess.run(cmd, cwd=cwd, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=600)
    d = json.loads(p.stdout)
    text = d.get("result") or ""
    m = re.findall(r"VERDICT:\s*(PASS|FAIL)", text)
    return (m[-1] == "PASS") if m else None, float(d.get("total_cost_usd") or 0.0), list((d.get("modelUsage") or {}).keys())


def main(argv):
    if len(argv) != 4:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    case_yaml, scaffold, work = argv[1], argv[2], argv[3]
    if not os.path.isdir(work):
        print(json.dumps({"verdict": "COULD NOT RUN", "reason": "no work directory", "votes": [], "cost_usd": 0.0}))
        return 2
    files = changes(scaffold, work)
    prompt = (criteria_of(case_yaml) + "\n\nAgent output (files):\n" + (files or "(no file changes)"))
    votes, cost, models = [], 0.0, set()
    with tempfile.TemporaryDirectory(prefix="routing-judge-cwd-", ignore_cleanup_errors=True) as cwd:
        for _ in range(VOTES):
            v, c, ms = vote(prompt, cwd)
            votes.append(v)
            cost += c
            models.update(ms)
    passes = sum(1 for v in votes if v is True)
    verdict = "PASS" if passes * 2 > VOTES else "FAIL"
    print(json.dumps({"verdict": verdict, "votes": votes, "cost_usd": round(cost, 6), "models": sorted(models),
                      "changed_chars": len(files)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
