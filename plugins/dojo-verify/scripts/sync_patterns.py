#!/usr/bin/env python3
"""Regenerate the TypeScript copies of the shared tables from their JSON sources.

hooks/patterns.json  -> hooks/patterns.ts   (the mod cannot read files or import JSON)
tests/cases.json     -> tests/cases.ts      (the mod kit tests share the Python case table)

Edit the JSON, run this script, commit both. A unit test fails when the copies drift.
Usage: python3 scripts/sync_patterns.py [--check]
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TARGETS = [
    ("hooks/patterns.json", "hooks/patterns.ts", "PATTERNS", "patterns.json"),
    ("tests/cases.json", "tests/cases.ts", "CASES", "cases.json"),
]

HEADER = (
    "// Generated from %s by scripts/sync_patterns.py. Do not edit here: edit the JSON, run the script.\n"
    "// A unit test fails when this copy and the JSON differ.\n"
)


def render(src_name, const, label):
    with open(os.path.join(ROOT, src_name), "r") as fh:
        data = json.load(fh)
    body = json.dumps(data, indent=2, ensure_ascii=True)
    if "*/" in body:
        raise SystemExit("refusing: table contains a comment terminator")
    return (
        HEADER % label
        + "export const %s: any = (\n// BEGIN %s\n%s\n// END %s\n)\n" % (const, label, body, label)
    )


def main(argv):
    check = "--check" in argv
    dirty = False
    for src, dst, const, label in TARGETS:
        text = render(src, const, label)
        path = os.path.join(ROOT, dst)
        current = open(path, "r").read() if os.path.exists(path) else None
        if current == text:
            continue
        dirty = True
        if check:
            print("out of date: %s" % dst)
        else:
            with open(path, "w") as fh:
                fh.write(text)
            print("wrote %s" % dst)
    return 1 if (check and dirty) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
