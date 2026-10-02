#!/usr/bin/env python3
"""
face-parity.py — dual-navigability gate for the Dojo Genesis plugin corpus.

The corpus has ONE source of truth (the plugin directories on disk under
plugins/) and three faces that describe it:

  machine face  .claude-plugin/marketplace.json  (what installers consume)
  agent face    llms.txt                         (what LLMs ingest)
  human face    README.md                        (what people read)

All three have drifted from disk before (README said 92/9 and llms.txt 84/8
while disk held 97 — hand-repaired 2026-07-04, and the repair itself missed
two body claims). This gate makes that class of drift fail closed instead of
waiting for the next hand-audit. Pattern: one source, N faces, one gate.

Since 2.0.0 the marketplace has three groups, set by each entry's `category`:
suite (the protocol suite), library (the practice skills) and companion
(bring-loop, kata-harness). A count claim can name a group ("9 library
plugins"); it is then checked against that group, not the whole corpus.

Checks
  1  marketplace.json: every registered plugin exists on disk with a
     .claude-plugin/plugin.json and something to install (a skill, agent,
     command, workflow, or a dependency list)
  2  disk: every plugins/*/ dir holding a plugin.json is either registered
     in marketplace.json or consciously allowlisted as unregistered
  3  count claims: every "N ... skills" / "N ... plugins" number in the three
     faces matches computed disk truth (numbers at per-plugin scale exempt;
     a claim that names a group is checked against that group)
  4  README's per-plugin table: each row's own skill count matches that
     plugin's disk-computed count — closes the gap check 3 leaves open,
     since per-plugin-scale numbers are exempt there by design (this is
     exactly the drift vector that survived a 92-summed-to-94 table while
     the corpus-scale headline read 99, undetected until a hand audit)
  5  llms.txt "## Plugins (N)" header + its bullet list (scoped to that
     section body, not the whole file) match the registered set exactly
  6  README's version line matches marketplace.json metadata.version
  7  README's suite table (between the suite-table markers) is exactly what
     scripts/suite_table.py generates from the suite plugins on disk

Exit 0 = CONTRACT PASS, 1 = CONTRACT FAIL. Stdlib only, by design.
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
# marketplace.json. community-skills: dormant by design, and removed from the
# public repo in 2.0.0 (history keeps it); the entry stays only so the gate
# still passes in a checkout where that directory has not been deleted yet.
ALLOWLIST_UNREGISTERED = {"community-skills"}

GROUPS = ("suite", "library", "companion")

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
    group_of: dict[str, str] = {}
    for entry in market.get("plugins", []):
        name, source = entry["name"], entry["source"]
        group_of[name] = entry.get("category", "")
        if group_of[name] not in GROUPS:
            fail(f"marketplace.json: '{name}' has category '{group_of[name]}', expected one of {list(GROUPS)}")
        pdir = (ROOT / source).resolve()
        pjson = pdir / ".claude-plugin" / "plugin.json"
        if not pjson.is_file():
            fail(f"marketplace.json registers '{name}' but {source}/.claude-plugin/plugin.json is missing on disk")
            continue
        count = len(list((pdir / "skills").glob("*/SKILL.md")))
        skills_per_plugin[name] = count
        has_other = (any((pdir / "agents").glob("*.md")) or any((pdir / "commands").glob("*.md"))
                     or any((pdir / "workflows").glob("*.js")))
        try:
            has_deps = bool(json.loads(pjson.read_text(encoding="utf-8")).get("dependencies"))
        except ValueError:
            has_deps = False
        if count == 0 and not (has_other or has_deps):
            fail(f"registered plugin '{name}' ships nothing on disk (no skills, agents, commands, workflows or dependencies)")
    if len(skills_per_plugin) == len(registered):
        ok(f"marketplace.json: all {len(registered)} registered plugins exist on disk with something to install")

    total_skills = sum(skills_per_plugin.values())
    total_plugins = len(registered)
    per_plugin_max = max(skills_per_plugin.values(), default=0)
    group_plugins = {g: sum(1 for n in registered if group_of.get(n) == g) for g in GROUPS}
    group_skills = {g: sum(c for n, c in skills_per_plugin.items() if group_of.get(n) == g) for g in GROUPS}
    print(f"       disk truth: {total_skills} skills across {total_plugins} registered plugins "
          f"(largest plugin: {per_plugin_max} skills)")
    print("       groups: " + ", ".join(f"{g} {group_plugins[g]} plugins / {group_skills[g]} skills" for g in GROUPS))

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
    # treated as per-plugin references and exempted. A claim that names a
    # group (suite, library, companion) in those words is checked against
    # that group's count instead, and is never exempt.
    skills_re = re.compile(r"\b(\d+)((?:\s+[A-Za-z-]+){0,3}?)\s+skills\b", re.IGNORECASE)
    plugins_re = re.compile(r"\b(\d+)((?:\s+[A-Za-z-]+){0,2}?)\s+plugins\b", re.IGNORECASE)

    def named_group(words: str):
        for w in words.lower().split():
            if w in GROUPS:
                return w
        return None

    claims_checked = 0
    for face in (MARKETPLACE, LLMS, README):
        rel = face.relative_to(ROOT)
        for lineno, line in enumerate(face.read_text(encoding="utf-8").splitlines(), 1):
            for m in skills_re.finditer(line):
                n = int(m.group(1))
                grp = named_group(m.group(2))
                if grp:
                    claims_checked += 1
                    if n != group_skills[grp]:
                        fail(f"{rel}:{lineno} {grp} skills claim says {n}, disk truth is {group_skills[grp]}")
                    continue
                if n <= per_plugin_max:
                    continue  # plausibly a per-plugin count, not a corpus claim
                claims_checked += 1
                if n != total_skills:
                    fail(f"{rel}:{lineno} skills claim says {n}, disk truth is {total_skills}")
            for m in plugins_re.finditer(line):
                n = int(m.group(1))
                grp = named_group(m.group(2))
                claims_checked += 1
                want = group_plugins[grp] if grp else total_plugins
                if n != want:
                    fail(f"{rel}:{lineno} {grp or 'registered'} plugins claim says {n}, disk truth is {want}")
    ok(f"count claims: {claims_checked} corpus-scale claims swept across the three faces")

    # ---- README per-plugin table parity -----------------------------------
    # Check 3 exempts numbers <= per_plugin_max as "plausibly a per-plugin
    # count" — that exemption is exactly where per-plugin drift survived
    # undetected before. This check targets the table directly: every row's
    # own claimed count must match that plugin's disk-computed skill count.
    row_re = re.compile(
        r"^\|\s*\[([a-z0-9-]+)\]\(plugins/[a-z0-9-]+/?\)\s*\|[^|]*\|\s*(\d+)\s*\|"
    )
    readme_text = README.read_text(encoding="utf-8")
    found_rows: dict[str, int] = {}
    for lineno, line in enumerate(readme_text.splitlines(), 1):
        m = row_re.match(line)
        if not m:
            continue
        name, claimed = m.group(1), int(m.group(2))
        found_rows[name] = lineno
        if name not in skills_per_plugin:
            continue
        actual = skills_per_plugin[name]
        if claimed != actual:
            fail(f"README.md:{lineno} per-plugin table says '{name}' has {claimed} skills, disk truth is {actual}")

    missing_rows = set(registered) - set(found_rows)
    if missing_rows:
        fail(f"README.md per-plugin table missing row(s) for: {sorted(missing_rows)}")
    elif found_rows:
        ok(f"README.md per-plugin table: {len(found_rows)} rows match disk-computed per-plugin counts")
    else:
        fail("README.md: no per-plugin table rows found — table format may have changed")

    # ---- llms.txt plugin list parity -------------------------------------
    # Bullet extraction is scoped to the "## Plugins (N)" section body only
    # (up to the next "## " header), not the whole file — llms.txt legitimately
    # has other "- **bold**" bullets elsewhere (e.g. the "## Clusters" section's
    # cluster-id bullets), which must not be mistaken for plugin-list entries.
    llms_text = LLMS.read_text(encoding="utf-8")
    header = re.search(r"^##\s+Plugins\s+\((\d+)\)\s*$", llms_text, re.MULTILINE)
    if not header:
        fail("llms.txt: no '## Plugins (N)' header found")
    else:
        if int(header.group(1)) != total_plugins:
            fail(f"llms.txt: '## Plugins ({header.group(1)})' header != registered count {total_plugins}")
        next_header = re.search(r"^##\s+", llms_text[header.end():], re.MULTILINE)
        section_end = header.end() + next_header.start() if next_header else len(llms_text)
        plugins_section = llms_text[header.end():section_end]
        listed = set(re.findall(r"^-\s+\*\*([a-z0-9-]+)\*\*", plugins_section, re.MULTILINE))
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

    # ---- README suite table ------------------------------------------------
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import suite_table
        problems = suite_table.check_readme(str(ROOT))
    except Exception as e:  # noqa: BLE001 - a table that cannot be generated is a failure, not a crash
        problems = [f"suite table could not be checked: {e}"]
    for pr in problems:
        fail(pr)
    if not problems:
        ok("README suite table: matches what scripts/suite_table.py generates from disk")

    # ---- verdict ----------------------------------------------------------
    print()
    if findings:
        print(f"CONTRACT FAIL ({len(findings)} finding(s))")
        return 1
    print(f"CONTRACT PASS ({len(passes)} checks, {claims_checked} claims verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
