#!/usr/bin/env python3
"""always_on.py: measure what every marketplace plugin adds to every session, and hold it to a budget.

usage:
  always_on.py [--repo DIR] [--claude BIN]            print the table; exit 1 if over budget
  always_on.py [--repo DIR] [--claude BIN] --write    also rewrite the table block in ALWAYS-ON.md

Always-on weight is the text a plugin puts in the model's context before you type anything. It has
two parts, measured separately:

  listing    skill, agent and command descriptions. Measured by `claude plugin details`, the same
             estimate the CLI shows anyone who runs it, read from its "Always-on:" line.
  injection  what the plugin's SessionStart command hooks print, run once in an empty project
             with an empty HOME, so no DOJO.md or per-user setup is read. `claude plugin details`
             labels hooks "no model context cost", which is not true of a SessionStart hook that
             returns additionalContext, so it is counted here. Tokens are characters / 3.5,
             rounded up: an estimate, close to what the CLI's estimator gives for English prose.

Budget (ADR 039 D7': "the always-on budget"; the paper's D8 action item):
  - the suite (every marketplace entry with category "suite", together) is under SUITE_BUDGET;
  - every other marketplace plugin is under PLUGIN_BUDGET on its own.
So the suite plus any three other plugins stays under 5,000 tokens.

Exit 0 within budget, 1 over budget, 2 could not run. Python 3.9, standard library only.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile

SUITE_BUDGET = 2000
PLUGIN_BUDGET = 1000
CHARS_PER_TOKEN = 3.5

BEGIN = "<!-- always-on:begin -->"
END = "<!-- always-on:end -->"
ALWAYS_RE = re.compile(r"Always-on:\s*~?([\d,]+)\s*tok")


class RunError(Exception):
    pass


def listing_tokens(claude, repo, name):
    pdir = os.path.join(repo, "plugins", name)
    try:
        out = subprocess.run([claude, "--plugin-dir", pdir, "plugin", "details", name],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True, timeout=120).stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RunError("%s: claude plugin details did not run (%s)" % (name, e.__class__.__name__))
    m = ALWAYS_RE.search(out)
    if not m:
        raise RunError("%s: no 'Always-on:' line in claude plugin details output" % name)
    return int(m.group(1).replace(",", ""))


def session_start_commands(pdir):
    path = os.path.join(pdir, "hooks", "hooks.json")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cmds = []
    for group in (data.get("hooks") or {}).get("SessionStart") or []:
        for h in group.get("hooks") or []:
            if h.get("type") == "command" and h.get("command"):
                cmds.append(h["command"])
    return cmds


def injected_text(stdout):
    s = stdout.strip()
    if not s:
        return ""
    try:
        data = json.loads(s)
    except ValueError:
        return s  # plain stdout from a SessionStart hook is added to context as is
    if not isinstance(data, dict):
        return s
    hso = data.get("hookSpecificOutput") or {}
    return hso.get("additionalContext") or ""


def injection_chars(pdir):
    total = 0
    with tempfile.TemporaryDirectory() as tmp:
        proj = os.path.join(tmp, "project")
        home = os.path.join(tmp, "home")
        os.mkdir(proj)
        os.mkdir(home)
        env = {"PATH": os.environ.get("PATH", ""), "HOME": home,
               "CLAUDE_PLUGIN_ROOT": pdir, "CLAUDE_PROJECT_DIR": proj}
        payload = json.dumps({"session_id": "always-on", "cwd": proj,
                              "hook_event_name": "SessionStart", "source": "startup"})
        for cmd in session_start_commands(pdir):
            try:
                r = subprocess.run(cmd, shell=True, cwd=proj, env=env, input=payload,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   universal_newlines=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired) as e:
                raise RunError("%s: SessionStart hook did not run (%s)" % (os.path.basename(pdir), e.__class__.__name__))
            if r.returncode == 0:
                total += len(injected_text(r.stdout))
    return total


def measure(repo, claude):
    with open(os.path.join(repo, ".claude-plugin", "marketplace.json"), encoding="utf-8") as f:
        market = json.load(f)
    rows = []
    for p in market.get("plugins") or []:
        name = p["name"]
        pdir = os.path.join(repo, "plugins", name)
        if not os.path.isdir(pdir):
            raise RunError("%s: listed in marketplace.json but not under plugins/" % name)
        listing = listing_tokens(claude, repo, name)
        chars = injection_chars(pdir)
        inj = int(math.ceil(chars / CHARS_PER_TOKEN))
        rows.append({"name": name, "category": p.get("category") or "", "listing": listing,
                     "injection": inj, "total": listing + inj})
    return rows


def judge(rows):
    problems = []
    suite = sum(r["total"] for r in rows if r["category"] == "suite")
    if suite >= SUITE_BUDGET:
        problems.append("suite: ~%d tokens (budget is under %d)" % (suite, SUITE_BUDGET))
    for r in rows:
        if r["category"] != "suite" and r["total"] >= PLUGIN_BUDGET:
            problems.append("%s: ~%d tokens (budget is under %d)" % (r["name"], r["total"], PLUGIN_BUDGET))
    return suite, problems


def table(rows, suite):
    lines = ["| Plugin | Group | Listing | SessionStart | Always-on |",
             "|--------|-------|--------:|-------------:|----------:|"]
    for r in rows:
        lines.append("| %s | %s | ~%s | %s | ~%s |" % (
            r["name"], r["category"], format(r["listing"], ","),
            ("~" + format(r["injection"], ",")) if r["injection"] else "0", format(r["total"], ",")))
    allsum = sum(r["total"] for r in rows)
    lines.append("")
    lines.append("Suite together: **~%s tokens** (budget: under %s). Each other plugin: budget under %s. "
                 "Everything in the marketplace installed at once: ~%s tokens."
                 % (format(suite, ","), format(SUITE_BUDGET, ","), format(PLUGIN_BUDGET, ","), format(allsum, ",")))
    return "\n".join(lines)


def write_block(path, block):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    i, j = text.find(BEGIN), text.find(END)
    if i < 0 or j < i:
        raise RunError("%s: missing %s / %s markers" % (path, BEGIN, END))
    new = text[:i + len(BEGIN)] + "\n" + block + "\n" + text[j:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--claude", default=os.environ.get("CLAUDE_BIN") or "claude")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    try:
        rows = measure(a.repo, a.claude)
        suite, problems = judge(rows)
        block = table(rows, suite)
        print(block)
        if a.write:
            write_block(os.path.join(a.repo, "ALWAYS-ON.md"), block)
    except (RunError, OSError, ValueError, KeyError) as e:
        print("always-on: could not run: %s" % e, file=sys.stderr)
        return 2
    for p in problems:
        print("over budget: " + p)
    print("always-on: suite ~%d tokens, %d plugin(s), %d over budget" % (suite, len(rows), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
