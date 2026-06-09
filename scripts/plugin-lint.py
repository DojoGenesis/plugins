#!/usr/bin/env python3
"""
plugin-lint.py — CoworkPluginsByDojoGenesis integrity linter
stdlib only, Python 3.8+

Exit codes:
  0 — all checks passed (warnings allowed)
  1 — warnings only (no failures)
  2 — one or more failures
"""

import json
import os
import re
import sys
from pathlib import Path

# ─── Tunables ───────────────────────────────────────────────────────────────
DESCRIPTION_MAX_CHARS = 1024
REPO_ROOT = Path(__file__).resolve().parent.parent


# ─── Helpers ────────────────────────────────────────────────────────────────

def parse_frontmatter(text: str):
    """
    Extract YAML-style frontmatter between the first pair of --- delimiters.
    Returns the raw frontmatter string (without delimiters) or None if absent.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return None
    return "\n".join(lines[1:end])


def extract_frontmatter_field(frontmatter: str, field: str):
    """
    Extract a simple scalar value for a given field from a YAML-like frontmatter block.
    Only handles single-line values (covers 'name:' and 'description:').
    """
    pattern = re.compile(rf"^{re.escape(field)}\s*:\s*(.+)", re.MULTILINE)
    m = pattern.search(frontmatter)
    if m:
        return m.group(1).strip().strip('"').strip("'")
    return None


def extract_relative_paths(frontmatter: str):
    """
    Find any relative path strings matching scripts/... or references/... in frontmatter.
    """
    return re.findall(r"(?:scripts|references)/[^\s\"'>,]+", frontmatter)


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ─── Data collection ────────────────────────────────────────────────────────

def discover_plugins(plugins_dir: Path):
    """
    Return list of (plugin_dir: Path) for every subdirectory that has a
    .claude-plugin/plugin.json.
    """
    plugins = []
    for p in sorted(plugins_dir.iterdir()):
        if p.is_dir() and (p / ".claude-plugin" / "plugin.json").exists():
            plugins.append(p)
    return plugins


def collect_skills(plugin_dir: Path):
    """
    Return list of (skill_dir: Path, skill_md: Path | None) for every
    subdirectory under skills/.
    """
    skills_dir = plugin_dir / "skills"
    if not skills_dir.is_dir():
        return []
    results = []
    for s in sorted(skills_dir.iterdir()):
        if s.is_dir():
            md = s / "SKILL.md"
            results.append((s, md if md.exists() else None))
    return results


# ─── Checks ─────────────────────────────────────────────────────────────────

class LintResult:
    def __init__(self):
        self.failures = []   # (plugin, skill_or_none, message)
        self.warnings = []   # (plugin, skill_or_none, message)

    def fail(self, plugin, skill, msg):
        self.failures.append((plugin, skill, msg))

    def warn(self, plugin, skill, msg):
        self.warnings.append((plugin, skill, msg))

    @property
    def has_failures(self):
        return bool(self.failures)

    @property
    def has_warnings(self):
        return bool(self.warnings)


def check_plugin_manifest(plugin_dir: Path, result: LintResult):
    """
    Verify .claude-plugin/plugin.json has name and version fields.
    """
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    plugin_name = plugin_dir.name
    try:
        data = load_json(manifest_path)
    except (json.JSONDecodeError, OSError) as e:
        result.fail(plugin_name, None, f"plugin.json unreadable: {e}")
        return

    if not data.get("name"):
        result.fail(plugin_name, None, "plugin.json missing or empty 'name'")
    if not data.get("version"):
        result.fail(plugin_name, None, "plugin.json missing or empty 'version'")


def check_skill_frontmatter(plugin_dir: Path, skill_dir: Path, skill_md: Path,
                             result: LintResult):
    """
    Verify SKILL.md frontmatter:
    - exists
    - non-empty name: field
    - non-empty description: field
    - description <= DESCRIPTION_MAX_CHARS
    """
    plugin_name = plugin_dir.name
    skill_name = skill_dir.name
    rel = skill_md.relative_to(REPO_ROOT)

    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError as e:
        result.fail(plugin_name, skill_name, f"{rel} unreadable: {e}")
        return

    fm = parse_frontmatter(text)
    if fm is None:
        result.fail(plugin_name, skill_name, f"{rel} — missing frontmatter block (no opening/closing ---)")
        return

    name_val = extract_frontmatter_field(fm, "name")
    if not name_val:
        result.fail(plugin_name, skill_name, f"{rel} — frontmatter 'name' missing or empty")

    desc_val = extract_frontmatter_field(fm, "description")
    if not desc_val:
        result.fail(plugin_name, skill_name, f"{rel} — frontmatter 'description' missing or empty")
    elif len(desc_val) > DESCRIPTION_MAX_CHARS:
        result.fail(
            plugin_name, skill_name,
            f"{rel} — description exceeds {DESCRIPTION_MAX_CHARS} chars "
            f"(got {len(desc_val)})"
        )

    # Reference-path check (warn only)
    for ref_path in extract_relative_paths(fm):
        candidate = skill_dir / ref_path
        if not candidate.exists():
            result.warn(plugin_name, skill_name,
                        f"{rel} — references path '{ref_path}' not found "
                        f"relative to skill dir")


def check_skill_md_exists(plugin_dir: Path, skill_dir: Path, result: LintResult):
    plugin_name = plugin_dir.name
    skill_name = skill_dir.name
    rel = (skill_dir / "SKILL.md").relative_to(REPO_ROOT)
    result.fail(plugin_name, skill_name, f"{rel} — SKILL.md file missing")


def check_marketplace_consistency(marketplace_path: Path, plugins_dir: Path,
                                   result: LintResult):
    """
    Every plugin in marketplace.json must exist on disk, and every plugin
    dir on disk must be listed in marketplace.json.
    """
    try:
        data = load_json(marketplace_path)
    except (json.JSONDecodeError, OSError) as e:
        result.fail("marketplace", None, f"marketplace.json unreadable: {e}")
        return

    listed_plugins = data.get("plugins", [])
    listed_names = set()
    for entry in listed_plugins:
        n = entry.get("name")
        if n:
            listed_names.add(n)
            src = entry.get("source", "")
            # Resolve source relative to the repo root (marketplace.json's grandparent,
            # since the file lives at .claude-plugin/marketplace.json).
            repo_root = marketplace_path.parent.parent
            if src.startswith("./"):
                src_path = repo_root / src[2:]
            else:
                src_path = repo_root / src
            if not src_path.exists():
                result.fail("marketplace", n,
                            f"marketplace.json lists '{n}' (source='{src}') but path does not exist")

    # Every plugin dir on disk should be in marketplace.json
    disk_plugins = set()
    for p in plugins_dir.iterdir():
        if p.is_dir() and (p / ".claude-plugin" / "plugin.json").exists():
            disk_plugins.add(p.name)

    for name in sorted(disk_plugins - listed_names):
        result.fail("marketplace", name,
                    f"Plugin dir '{name}' exists on disk but is not listed in marketplace.json")

    for name in sorted(listed_names - disk_plugins):
        result.fail("marketplace", name,
                    f"marketplace.json lists '{name}' but no matching plugin dir found on disk")


def check_skill_name_collisions(all_skills: dict, result: LintResult):
    """
    all_skills: {skill_dir_name: [plugin_name, ...]}
    Any skill name appearing in 2+ plugins → FAIL.
    """
    for skill_name, plugins in sorted(all_skills.items()):
        if len(plugins) > 1:
            result.fail(
                "cross-plugin", skill_name,
                f"Skill directory name '{skill_name}' collides across plugins: "
                + ", ".join(sorted(plugins))
            )


# ─── Reporting ───────────────────────────────────────────────────────────────

def group_messages(messages):
    """Group (plugin, skill, msg) triples by plugin."""
    grouped = {}
    for plugin, skill, msg in messages:
        grouped.setdefault(plugin, []).append((skill, msg))
    return grouped


def print_report(result: LintResult, total_plugins: int, total_skills: int):
    print()
    print("=" * 72)
    print("plugin-lint report")
    print(f"  plugins scanned : {total_plugins}")
    print(f"  skills  scanned : {total_skills}")
    print("=" * 72)

    if result.has_failures:
        print(f"\nFAILURES ({len(result.failures)}):")
        for plugin, items in sorted(group_messages(result.failures).items()):
            print(f"\n  [{plugin}]")
            for skill, msg in items:
                prefix = f"    skill={skill}  " if skill else "    "
                print(f"{prefix}FAIL: {msg}")
    else:
        print("\n  No failures.")

    if result.has_warnings:
        print(f"\nWARNINGS ({len(result.warnings)}):")
        for plugin, items in sorted(group_messages(result.warnings).items()):
            print(f"\n  [{plugin}]")
            for skill, msg in items:
                prefix = f"    skill={skill}  " if skill else "    "
                print(f"{prefix}WARN: {msg}")
    else:
        print("  No warnings.")

    print()
    if result.has_failures:
        print("RESULT: FAILED")
    elif result.has_warnings:
        print("RESULT: PASSED WITH WARNINGS")
    else:
        print("RESULT: CLEAN")
    print("=" * 72)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    plugins_dir = REPO_ROOT / "plugins"
    marketplace_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"

    if not plugins_dir.is_dir():
        print(f"ERROR: plugins dir not found at {plugins_dir}", file=sys.stderr)
        sys.exit(2)

    result = LintResult()

    # Collect all plugins and skills
    plugins = discover_plugins(plugins_dir)
    all_skill_names: dict[str, list] = {}   # skill_dir_name → [plugin_name, ...]
    total_skills = 0

    for plugin_dir in plugins:
        # 1. Manifest check
        check_plugin_manifest(plugin_dir, result)

        # 2. Skill-level checks
        skills = collect_skills(plugin_dir)
        for skill_dir, skill_md in skills:
            total_skills += 1
            skill_dir_name = skill_dir.name
            all_skill_names.setdefault(skill_dir_name, []).append(plugin_dir.name)

            if skill_md is None:
                check_skill_md_exists(plugin_dir, skill_dir, result)
            else:
                check_skill_frontmatter(plugin_dir, skill_dir, skill_md, result)

    # 3. Cross-plugin collision detection
    check_skill_name_collisions(all_skill_names, result)

    # 4. Marketplace consistency
    if marketplace_path.exists():
        check_marketplace_consistency(marketplace_path, plugins_dir, result)
    else:
        result.fail("marketplace", None,
                    f"marketplace.json not found at {marketplace_path.relative_to(REPO_ROOT)}")

    print_report(result, len(plugins), total_skills)

    if result.has_failures:
        sys.exit(2)
    elif result.has_warnings:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
