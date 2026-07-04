#!/usr/bin/env python3
"""
face-parity.py — dual-navigability gate for the CoworkPlugins corpus.

The corpus has ONE source of truth (the plugin directories on disk under
plugins/) and three faces that describe it:

  machine face  .claude-plugin/marketplace.json  (what installers consume)
  agent face    llms.txt                         (what LLMs ingest)
  human face    README.md                        (what people read)

All three have drifted from disk before (README said 92/9 and llms.txt 84/8
while disk held 97 — hand-repaired 2026-07-04, and the repair itself missed
two body claims). This gate makes that class of drift fail closed instead of
waiting for the next hand-audit. Pattern: seed_dual_navigability.md in
TresPies-AI-Orchestration — one source, N faces, one gate.

Checks
  1  marketplace.json: every registered plugin exists on disk with a
     .claude-plugin/plugin.json and at least one skill
  2  disk: every plugins/*/ dir holding a plugin.json is either registered
     in marketplace.json or consciously allowlisted as unregistered
  3  count claims: every "N ... skills" / "N ... plugins" number in the three
     faces matches computed disk truth (numbers at per-plugin scale exempt)
  4  llms.txt "## Plugins (N)" header + its bullet list match the registered
     set exactly
  5  README's version line matches marketplace.json metadata.version

Exit 0 = CONTRACT PASS, 1 = CONTRACT FAIL. Stdlib only, by design — same
posture as trespies-dev/scripts/validate_facet.py and the dag-essentials
check_verb_parity.py.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
LLMS = ROOT / "llms.txt"
README = ROOT / "README.md"

# Plugin dirs that hold a plugin.json but are deliberately NOT registered in
# marketplace.json. community-skills: ~599 harvested skills, dormant by design
# (wholesale registration floods context budgets and fails plugin-lint; skills
# are promoted individually into the registered plugins instead).
ALLOWLIST_UNREGISTERED = {"community-skills"}

findings: list[str] = []
passes: list[str] = []


def fail(msg: str) -> None:
    findings.append(msg)
    print(f"[FAIL] {msg}")


def ok(msg: str) -> None:
    passes.append(msg)
    print(f"[PASS] {msg}")


def main() -> int:
    # ---- source of truth: disk ------------------------------------------
    market = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    registered = [p["name"] for p in market.get("plugins", [])]
    version = market.get("metadata", {}).get("version", "")

    skills_per_plugin: dict[str, int] = {}
    for entry in market.get("plugins", []):
        name, source = entry["name"], entry["source"]
        pdir = (ROOT / source).resolve()
        if not (pdir / ".claude-plugin" / "plugin.json").is_file():
            fail(f"marketplace.json registers '{name}' but {source}/.claude-plugin/plugin.json is missing on disk")
            continue
        count = len(list((pdir / "skills").glob("*/SKILL.md")))
        skills_per_plugin[name] = count
        if count == 0:
            fail(f"registered plugin '{name}' has zero skills on disk")
    if len(skills_per_plugin) == len(registered):
        ok(f"marketplace.json: all {len(registered)} registered plugins exist on disk with skills")

    total_skills = sum(skills_per_plugin.values())
    total_plugins = len(registered)
    per_plugin_max = max(skills_per_plugin.values(), default=0)
    print(f"       disk truth: {total_skills} skills across {total_plugins} registered plugins "
          f"(largest plugin: {per_plugin_max} skills)")

    # ---- disk dirs vs registry ------------------------------------------
    on_disk = {d.name for d in (ROOT / "plugins").iterdir()
               if (d / ".claude-plugin" / "plugin.json").is_file()}
    unregistered = on_disk - set(registered)
    rogue = unregistered - ALLOWLIST_UNREGISTERED
    if rogue:
        fail(f"plugin dirs on disk neither registered nor allowlisted: {sorted(rogue)} "
             f"(register in marketplace.json or add to ALLOWLIST_UNREGISTERED consciously)")
    else:
        ok(f"disk<->registry: {len(on_disk)} plugin dirs = {total_plugins} registered "
           f"+ {sorted(unregistered) or 'none'} allowlisted-unregistered")

    # ---- count claims in the three faces --------------------------------
    # Any "N <up to 3 words> skills" claim above per-plugin scale must equal
    # the corpus total; any "N <up to 2 words> plugins" claim must equal the
    # registered count. Numbers at or below the largest single plugin are
    # treated as per-plugin references and exempted.
    skills_re = re.compile(r"\b(\d+)(?:\s+[A-Za-z-]+){0,3}?\s+skills\b", re.IGNORECASE)
    plugins_re = re.compile(r"\b(\d+)(?:\s+[A-Za-z-]+){0,2}?\s+plugins\b", re.IGNORECASE)

    claims_checked = 0
    for face in (MARKETPLACE, LLMS, README):
        rel = face.relative_to(ROOT)
        for lineno, line in enumerate(face.read_text(encoding="utf-8").splitlines(), 1):
            for m in skills_re.finditer(line):
                n = int(m.group(1))
                if n <= per_plugin_max:
                    continue  # plausibly a per-plugin count, not a corpus claim
                claims_checked += 1
                if n != total_skills:
                    fail(f"{rel}:{lineno} skills claim says {n}, disk truth is {total_skills}")
            for m in plugins_re.finditer(line):
                n = int(m.group(1))
                claims_checked += 1
                if n != total_plugins:
                    fail(f"{rel}:{lineno} plugins claim says {n}, registered count is {total_plugins}")
    ok(f"count claims: {claims_checked} corpus-scale claims swept across the three faces")

    # ---- llms.txt plugin list parity -------------------------------------
    llms_text = LLMS.read_text(encoding="utf-8")
    header = re.search(r"^##\s+Plugins\s+\((\d+)\)\s*$", llms_text, re.MULTILINE)
    if not header:
        fail("llms.txt: no '## Plugins (N)' header found")
    elif int(header.group(1)) != total_plugins:
        fail(f"llms.txt: '## Plugins ({header.group(1)})' header != registered count {total_plugins}")
    listed = set(re.findall(r"^-\s+\*\*([a-z0-9-]+)\*\*", llms_text, re.MULTILINE))
    if listed != set(registered):
        missing = set(registered) - listed
        extra = listed - set(registered)
        fail(f"llms.txt plugin list != registered set (missing: {sorted(missing) or 'none'}, extra: {sorted(extra) or 'none'})")
    else:
        ok(f"llms.txt: header count + bullet list match the {total_plugins} registered plugins")

    # ---- README version line ---------------------------------------------
    ver_line = re.search(r"^\*\*(\d+\.\d+\.\d+)\*\*\s+—", README.read_text(encoding="utf-8"), re.MULTILINE)
    if not ver_line:
        fail("README.md: no '**X.Y.Z** —' version line found")
    elif ver_line.group(1) != version:
        fail(f"README.md version line says {ver_line.group(1)}, marketplace.json metadata.version is {version}")
    else:
        ok(f"version: README line matches marketplace.json ({version})")

    # ---- verdict ----------------------------------------------------------
    print()
    if findings:
        print(f"CONTRACT FAIL ({len(findings)} finding(s))")
        return 1
    print(f"CONTRACT PASS ({len(passes)} checks, {claims_checked} claims verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
