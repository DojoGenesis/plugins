#!/usr/bin/env python3
"""suite_table.py: generate the README suite table from the plugin directories on disk.

usage:
  suite_table.py [--repo DIR]            print the table to stdout
  suite_table.py [--repo DIR] --write    rewrite the block between the suite-table markers in README.md
  suite_table.py [--repo DIR] --check    exit 1 if README.md's block differs from what disk produces

Only marketplace entries whose category is "suite" are listed, in marketplace order. Every cell
that carries a number is counted from files: skills/*/SKILL.md, agents/*.md, commands/*.md,
workflows/*.js, hooks/guards.json (a JSON list of guard ids) and the hook commands in
hooks/hooks.json. The job text is the plugin.json description, word for word. A mod is a
hooks/register.ts file; that is the whole definition of "mod" here.

Exit 0 ok, 1 --check found a difference, 2 could not run. Python 3.9, standard library only.
"""
import argparse
import json
import os
import sys

BEGIN = "<!-- suite-table:begin -->"
END = "<!-- suite-table:end -->"
HEADER = ("| Plugin | Job | Skills | Also ships | Tier |\n"
          "|--------|-----|--------|------------|------|")


class TableError(Exception):
    pass


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise TableError("%s: cannot read as JSON (%s)" % (path, e.__class__.__name__))


def count_dir(d, sub, suffix=None, nested=None):
    base = os.path.join(d, sub)
    if not os.path.isdir(base):
        return 0
    n = 0
    for name in os.listdir(base):
        p = os.path.join(base, name)
        if nested:
            if os.path.isdir(p) and os.path.isfile(os.path.join(p, nested)):
                n += 1
        elif os.path.isfile(p) and name.endswith(suffix):
            n += 1
    return n


def hook_commands(d):
    path = os.path.join(d, "hooks", "hooks.json")
    if not os.path.isfile(path):
        return 0
    data = load_json(path)
    cmds = set()
    for groups in (data.get("hooks") or {}).values():
        for g in groups:
            for h in g.get("hooks", []):
                if h.get("command"):
                    cmds.add(h["command"])
    return len(cmds)


def plural(n, word):
    return "%d %s" % (n, word if n == 1 else word + "s")


def describe(repo, entry):
    d = os.path.normpath(os.path.join(repo, entry["source"]))
    pj = load_json(os.path.join(d, ".claude-plugin", "plugin.json"))
    deps = pj.get("dependencies") or []
    skills = count_dir(d, "skills", nested="SKILL.md")
    agents = count_dir(d, "agents", ".md")
    commands = count_dir(d, "commands", ".md")
    workflows = count_dir(d, "workflows", ".js")
    guards = None
    gp = os.path.join(d, "hooks", "guards.json")
    if os.path.isfile(gp):
        g = load_json(gp)
        if not isinstance(g, list):
            raise TableError("%s: guards.json must be a JSON list" % entry["name"])
        guards = len(set(g))
    hooks = hook_commands(d)
    mod = os.path.isfile(os.path.join(d, "hooks", "register.ts"))
    parts = []
    if deps:
        parts.append(plural(len(deps), "dependency").replace("dependencys", "dependencies"))
    if agents:
        parts.append(plural(agents, "agent"))
    if commands:
        parts.append(plural(commands, "command"))
    if workflows:
        parts.append(plural(workflows, "workflow"))
    if guards is not None:
        parts.append(plural(guards, "guard"))
    elif hooks:
        parts.append(plural(hooks, "hook"))
    if deps:
        tier = "bundle"
    elif mod:
        tier = "classic + mod (early access)"
    elif workflows:
        tier = "workflows"
    else:
        tier = "classic"
    return dict(name=entry["name"], job=str(pj.get("description", "")).replace("|", "\\|"),
                skills=skills, also=", ".join(parts) if parts else "none", tier=tier)


def suite_rows(repo):
    market = load_json(os.path.join(repo, ".claude-plugin", "marketplace.json"))
    rows = [describe(repo, e) for e in market.get("plugins", []) if e.get("category") == "suite"]
    if not rows:
        raise TableError("marketplace.json lists no plugin with category suite")
    return rows


def render(rows):
    lines = [HEADER]
    for r in rows:
        lines.append("| [%(name)s](plugins/%(name)s/) | %(job)s | %(skills)d | %(also)s | %(tier)s |" % r)
    return "\n".join(lines)


def block(repo):
    return BEGIN + "\n" + render(suite_rows(repo)) + "\n" + END


def split_readme(text):
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(END) < text.index(BEGIN):
        raise TableError("README.md needs exactly one suite-table:begin and one suite-table:end marker, in order")
    b = text.index(BEGIN)
    e = text.index(END) + len(END)
    return text[:b], text[b:e], text[e:]


def check_readme(repo):
    """Return a list of problems (empty when README matches disk)."""
    path = os.path.join(repo, "README.md")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise TableError("README.md unreadable (%s)" % e.__class__.__name__)
    _, current, _ = split_readme(text)
    want = block(repo)
    if current == want:
        return []
    cur, new = current.split("\n"), want.split("\n")
    out = []
    for i in range(max(len(cur), len(new))):
        a = cur[i] if i < len(cur) else "(missing)"
        b = new[i] if i < len(new) else "(extra line)"
        if a != b:
            out.append("README.md suite table line %d differs from disk: %s" % (i + 1, b[:90]))
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    repo = os.path.abspath(a.repo)
    try:
        if a.check:
            problems = check_readme(repo)
            for p in problems:
                print("suite_table: " + p)
            if not problems:
                print("suite_table: README suite table matches disk")
            return 1 if problems else 0
        if a.write:
            path = os.path.join(repo, "README.md")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            head, _, tail = split_readme(text)
            with open(path, "w", encoding="utf-8") as f:
                f.write(head + block(repo) + tail)
            print("suite_table: wrote README.md suite table")
            return 0
        print(render(suite_rows(repo)))
        return 0
    except TableError as e:
        print("suite_table: could not run: %s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
