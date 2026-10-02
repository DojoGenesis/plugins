#!/usr/bin/env python3
"""Write the TypeScript copies of the shared tables from their JSON sources.

scripts/pricing.json     -> hooks/pricing.ts   (a mod cannot import JSON; only source files load)
tests/model_vectors.json -> tests/vectors.ts   (the kit tests read the same vectors as the Python tests)

Edit the JSON, run this script, keep both. `--check` exits 1 when a copy is out of date; a unit test runs it.
Standard library only, Python 3.9 or newer.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HEADER = (
    "// Generated from %s by scripts/gen_pricing_ts.py. Generated, do not edit here:\n"
    "// edit the JSON and run the script. A unit test fails when this copy and the JSON differ.\n"
)

TARGETS = [
    # (source, destination, exported const, type annotation)
    ("scripts/pricing.json", "hooks/pricing.ts", "PRICING",
     "{ source: string; unit: string; cache_write_5m_multiplier: number; cache_write_1h_multiplier: number;"
     " models: Record<string, { input: number; output: number; cache_read: number }> }"),
    ("tests/model_vectors.json", "tests/vectors.ts", "VECTORS",
     "{ comment: string; normalize: [string, string][]; priced: [string, string | null][]; tiers: [string, string][] }"),
]


def render(source, const, annotation):
    with open(os.path.join(ROOT, source), "r") as handle:
        data = json.load(handle)
    body = json.dumps(data, indent=2, ensure_ascii=True)
    return (HEADER % source) + "export const %s: %s = %s\n" % (const, annotation, body)


def main(argv):
    check = "--check" in argv
    root = ROOT
    for arg in argv:
        if arg.startswith("--root="):
            root = arg.split("=", 1)[1]
    dirty = False
    for source, dest, const, annotation in TARGETS:
        text = render(source, const, annotation)
        path = os.path.join(root, dest)
        current = None
        if os.path.exists(path):
            with open(path, "r") as handle:
                current = handle.read()
        if current == text:
            continue
        dirty = True
        if check:
            print("out of date: %s" % dest)
        else:
            with open(path, "w") as handle:
                handle.write(text)
            print("wrote %s" % dest)
    return 1 if (check and dirty) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
