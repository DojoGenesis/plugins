#!/usr/bin/env python3
"""suite_lint.py: structural linter for the Dojo suite plugins.

Usage:
  suite_lint.py [PLUGIN ...] [--json] [--skip RULE[,RULE]] [--repo PATH]

PLUGIN is a plugin name (resolved under <repo>/plugins/) or a path to a plugin
directory. With no PLUGIN, the eight suite plugins and the dependency-only
dojo-suite plugin are linted; one that is missing on disk is an error. Any other
plugins/dojo-* directory gets a one-line note and is not linted.

dojo-suite carries a manifest and nothing else. It is exempt from the kill-switch
and always-on budget rules, and these extra rules apply to it: every dependency
exists as a plugin directory and, when .claude-plugin/marketplace.json exists, is
listed in it exactly once; every suite plugin is a dependency.

Exit codes: 0 clean, 1 defects found, 2 could not run (an empty run is never a
pass). Warnings never change the exit code.

Rule ids (for --skip; a prefix such as `py39` skips py39-compile and py39-pep604):
  manifest userconfig frontmatter skill agent command outputstyle budget hook
  plugin-root workflow py39-compile py39-pep604 py39-api internal-ref voice
  kill-switch hook-no-network mod junk evals plugin suite-deps suite-marketplace

The linter is structural: it checks shape, lengths, names and references. It does
not judge whether prose is good or whether a hook does what it says. Several rules
are heuristics: the skill-description verb check is a stoplist of non-verb starts,
the kill-switch check looks for the variable name in a code string, and the voice
scan matches a fixed phrase list. Terms from the local denylists are not handled
here; suite_denylist.py scans for them. Python 3.9 compatible, standard library only.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import posixpath
import re
import shlex
import subprocess
import sys
from pathlib import Path

SUITE = [
    "dojo-protocol", "dojo-gates", "dojo-router", "dojo-meter",
    "dojo-verify", "dojo-flow", "dojo-doctor", "dojo-settle",
]
# Dependency-only plugin: a manifest that depends on every SUITE member and ships nothing else.
META_PLUGIN = "dojo-suite"
LINTED_BY_DEFAULT = SUITE + [META_PLUGIN]
COMPONENT_DIRS = ("skills", "agents", "commands", "hooks", "workflows", "output-styles", "scripts", "evals", "tests")

# Public promise text, frozen by the build contract; plugin.json uses it verbatim.
PROMISES = {
    "dojo-protocol": "The Dojo Protocol for Claude Code: ten rules at session start, a scout→contract→build→verify spine, and role agents pinned to the right model.",
    "dojo-gates": "Deterministic guards for the mistakes that waste a day: blanket staging, rewriting pushed commits, printing secrets, oversized reads, silent probes.",
    "dojo-router": "No subagent silently inherits your most expensive model. Warns or blocks unpinned dispatches; the mod routes them by role.",
    "dojo-meter": "See what each turn, agent and model costs, and how big your context is: a cost report from your transcripts, and a live band with the mod.",
    "dojo-verify": "\"Done\" means a check ran and passed in this session. Flags claims of success with no evidence behind them.",
    "dojo-flow": "Parallel builds that stay independent: a contract gate, scouts on small models, builders in the middle, judges at the ends, and a scorecard that counts returns.",
    "dojo-doctor": "Find the hooks and settings that fail or cost you silently: broken interpreters, noisy injections, always-on token weight, flags that are off.",
    "dojo-settle": "Settle claims with evidence: pre-registered experiments, with/without baselines and decision gates before anything becomes a number.",
}

REPO_URL = "https://github.com/DojoGenesis/plugins"
HOMEPAGE_FMT = "https://dojogenesis.com/suite#%s"
AUTHOR_NAME = "Dojo Genesis"
LICENSE_ID = "Apache-2.0"

MODEL_ALIASES = ("haiku", "sonnet", "opus", "inherit")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
CONFIG_TYPES = ("string", "number", "boolean", "directory", "file")
INTERPRETERS = ("python3", "sh", "bash", "node")
BENIGN_SEGMENT_STARTS = ("true", "false", "exit", "echo", ":")
COMMON_EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "PostToolUseFailure", "InstructionsLoaded", "Stop")
# Manifest keys the dependency-only plugin may carry. Any other key (the component keys included) is an error.
SUITE_MANIFEST_KEYS = ("name", "version", "description", "author", "homepage", "repository", "license", "keywords", "dependencies", "displayName")
SUITE_ROOT_FILES = ("README.md", "LICENSE", "LICENSE.md", "LICENSE.txt")

SKILL_DESC_MAX = 250
OTHER_DESC_MAX = 200
SKILL_BODY_MAX = 6144
BUDGET_CHARS = 1000
SUITE_TOKEN_WARN = 3000
HOOK_TIMEOUT_WARN = 10
MAX_TEXT_BYTES = 4_000_000

NON_VERB_STARTS = frozenset("""
the a an this that these those it its your our my their his her we you they i he she there here
some any all each every no not when if while where which what who how why for with in on at to of
by from as and or but so than then also only just both either neither plus via per
""".split())

ERROR = "error"
WARN = "warning"


# ----------------------------------------------------------------------------
# Findings
# ----------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.items = []  # (plugin, rel, line, rule, severity, message)

    def add(self, plugin, rel, line, rule, sev, msg):
        self.items.append((plugin, rel or "", int(line or 1), rule, sev, msg))

    def error(self, plugin, rel, line, rule, msg):
        self.add(plugin, rel, line, rule, ERROR, msg)

    def warn(self, plugin, rel, line, rule, msg):
        self.add(plugin, rel, line, rule, WARN, msg)


def rule_skipped(rule, skips):
    for s in skips:
        if rule == s or rule.startswith(s + "-"):
            return True
    return False


# ----------------------------------------------------------------------------
# File helpers
# ----------------------------------------------------------------------------

def read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read(MAX_TEXT_BYTES + 1)
    except OSError:
        return None


def read_text(path):
    """Text of a file, or None when it is binary, huge or unreadable."""
    data = read_bytes(path)
    if data is None or len(data) > MAX_TEXT_BYTES:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", "replace")


def walk_plugin(root):
    """All files in a plugin as (absolute, relative-posix). Skips .git and node_modules."""
    out = []
    for dirpath, dirs, files in os.walk(str(root)):
        dirs[:] = sorted(d for d in dirs if d not in (".git", "node_modules"))
        for name in sorted(files):
            ab = os.path.join(dirpath, name)
            rel = os.path.relpath(ab, str(root)).replace(os.sep, "/")
            out.append((ab, rel))
    return out


def find_symlinks(root):
    """Every symlink in a plugin (file or directory links, never followed) as (relative-posix, target string)."""
    out = []
    for dirpath, dirs, files in os.walk(str(root), followlinks=False):
        keep = []
        for name in sorted(dirs) + sorted(files):
            ab = os.path.join(dirpath, name)
            if os.path.islink(ab):
                rel = os.path.relpath(ab, str(root)).replace(os.sep, "/")
                try:
                    out.append((rel, os.readlink(ab)))
                except OSError:
                    out.append((rel, ""))
            elif name in dirs and name not in (".git", "node_modules"):
                keep.append(name)
        dirs[:] = keep
    return out


def in_dir(rel, *names):
    first = rel.split("/", 1)[0]
    return first in names


# ----------------------------------------------------------------------------
# Frontmatter (strict, single-line values only)
# ----------------------------------------------------------------------------

_KEY_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.-]*):(?:[ \t]+(.*))?$")
_PLAIN_BAD_START = "`@%*&!"


def _parse_double(s):
    """s starts with a double quote. Returns (value, rest) or (None, None) when unclosed."""
    out = []
    i = 1
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "n":
                out.append("\n")
            elif n == "t":
                out.append("\t")
            elif n == "u" and re.match(r"[0-9a-fA-F]{4}$", s[i + 2:i + 6]):
                out.append(chr(int(s[i + 2:i + 6], 16)))
                i += 4
            else:
                out.append(n)
            i += 2
            continue
        if c == '"':
            return "".join(out), s[i + 1:]
        out.append(c)
        i += 1
    return None, None


def _parse_single(s):
    out = []
    i = 1
    while i < len(s):
        c = s[i]
        if c == "'":
            if i + 1 < len(s) and s[i + 1] == "'":
                out.append("'")
                i += 2
                continue
            return "".join(out), s[i + 1:]
        out.append(c)
        i += 1
    return None, None


def _split_flow(inner):
    items, cur, q, depth = [], [], None, 0
    for c in inner:
        if q:
            cur.append(c)
            if c == q:
                q = None
            continue
        if c in "\"'":
            q = c
            cur.append(c)
        elif c in "([":
            depth += 1
            cur.append(c)
        elif c in ")]":
            depth -= 1
            cur.append(c)
        elif c == "," and depth == 0:
            items.append("".join(cur))
            cur = []
        else:
            cur.append(c)
    items.append("".join(cur))
    return items, q


def parse_value(val):
    """Returns (value, error). value is str or list of str."""
    if val == "" or val.startswith("#"):
        return "", None
    c = val[0]
    if c in ">|":
        return None, "use a single-line value (block scalars are not accepted)"
    if c == '"':
        v, rest = _parse_double(val)
        if v is None:
            return None, "unclosed double quote"
        rest = rest.strip()
        if rest and not rest.startswith("#"):
            return None, "text after the closing quote"
        return v, None
    if c == "'":
        v, rest = _parse_single(val)
        if v is None:
            return None, "unclosed single quote"
        rest = rest.strip()
        if rest and not rest.startswith("#"):
            return None, "text after the closing quote"
        return v, None
    if c == "[":
        # find the matching ] outside quotes
        depth, q, end = 0, None, -1
        for i, ch in enumerate(val):
            if q:
                if ch == q:
                    q = None
                continue
            if ch in "\"'":
                q = ch
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end < 0:
            return None, "unclosed [ in flow list"
        rest = val[end + 1:].strip()
        if rest and not rest.startswith("#"):
            return None, "text after the closing ]"
        items, q = _split_flow(val[1:end])
        out = []
        for it in items:
            it = it.strip()
            if not it:
                continue
            if it[0] == '"':
                v, r = _parse_double(it)
                if v is None or r.strip():
                    return None, "bad quoted item in flow list"
                it = v
            elif it[0] == "'":
                v, r = _parse_single(it)
                if v is None or r.strip():
                    return None, "bad quoted item in flow list"
                it = v
            out.append(it)
        return out, None
    if c == "{":
        return None, "flow maps are not accepted; use a single-line value"
    if c in _PLAIN_BAD_START:
        return None, "unquoted value starts with %r; quote it" % c
    m = re.search(r"\s#", val)
    if m:
        val = val[:m.start()].rstrip()
    if ": " in val or val.endswith(":"):
        return None, "unquoted value contains ': '; quote the whole value"
    return val, None


class Fields(dict):
    """key -> (value, lineno); `bad` holds keys whose line failed to parse."""

    def __init__(self):
        dict.__init__(self)
        self.bad = set()


def parse_frontmatter(raw):
    """Parse a markdown file's frontmatter.

    Returns (fields, errors, body, body_start_line) where fields maps
    key -> (value, lineno) and errors is a list of (lineno, message).
    """
    errors = []
    fields = Fields()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return fields, [(1, "file is not valid UTF-8")], "", 1
    if text.startswith("﻿"):
        text = text[1:]
    if not text.strip():
        return fields, [(1, "file is empty")], "", 1
    lines = text.splitlines(keepends=True)
    if lines[0].strip() != "---":
        return fields, [(1, "frontmatter must start with --- on the first line")], text, 1
    close = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            close = i
            break
    if close is None:
        return fields, [(1, "frontmatter has no closing ---")], "", 1
    for i in range(1, close):
        ln = i + 1
        s = lines[i].rstrip("\r\n")
        if not s.strip():
            continue
        if s.lstrip().startswith("#") and not s[0].isspace():
            continue
        if s[0] in " \t":
            errors.append((ln, "indented line: use a single-line value"))
            continue
        if s.startswith("- ") or s == "-":
            errors.append((ln, "block lists are not accepted: use a single-line value or [a, b]"))
            continue
        m = _KEY_LINE.match(s)
        if not m:
            errors.append((ln, 'not a "key: value" line'))
            continue
        key = m.group(1)
        val, err = parse_value((m.group(2) or "").rstrip())
        if err:
            errors.append((ln, "%s: %s" % (key, err)))
            fields.bad.add(key)
            continue
        if key in fields:
            errors.append((ln, "duplicate key %s" % key))
            continue
        fields[key] = (val, ln)
    body = "".join(lines[close + 1:])
    return fields, errors, body, close + 2


def desc_of(fields):
    v = fields.get("description")
    if v is None:
        return None
    return v[0]


# ----------------------------------------------------------------------------
# Manifest
# ----------------------------------------------------------------------------

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_CFG_KEY = re.compile(r"^[a-z][a-z0-9_]*$")


def check_manifest(name, root, rep):
    rel = ".claude-plugin/plugin.json"
    path = root / ".claude-plugin" / "plugin.json"
    raw = read_bytes(path)
    if raw is None:
        rep.error(name, rel, 1, "manifest", "plugin.json is missing or unreadable")
        return None
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as e:
        rep.error(name, rel, 1, "manifest", "plugin.json is not valid JSON (%s)" % type(e).__name__)
        return None
    if not isinstance(data, dict):
        rep.error(name, rel, 1, "manifest", "plugin.json must be a JSON object")
        return None

    def need(field, typ, label):
        if field not in data:
            rep.error(name, rel, 1, "manifest", "missing required field: %s" % field)
            return False
        if not isinstance(data[field], typ):
            rep.error(name, rel, 1, "manifest", "%s must be %s" % (field, label))
            return False
        return True

    if need("name", str, "a string") and data["name"] != root.name:
        rep.error(name, rel, 1, "manifest", "name %r does not match the directory name %r" % (data["name"], root.name))
    if need("version", str, "a string") and not _SEMVER.match(data["version"]):
        rep.error(name, rel, 1, "manifest", "version %r is not MAJOR.MINOR.PATCH" % data["version"])
    if need("description", str, "a string"):
        d = data["description"]
        if len(d) > OTHER_DESC_MAX:
            rep.error(name, rel, 1, "manifest", "description is %d chars (max %d)" % (len(d), OTHER_DESC_MAX))
        if not d.strip():
            rep.error(name, rel, 1, "manifest", "description is empty")
        promise = PROMISES.get(root.name)
        if promise is not None and d != promise:
            rep.error(name, rel, 1, "manifest", "description is not the frozen promise text for %s" % root.name)
    if need("author", dict, "an object with name and email"):
        a = data["author"]
        if a.get("name") != AUTHOR_NAME:
            rep.error(name, rel, 1, "manifest", "author.name must be %r" % AUTHOR_NAME)
        em = a.get("email")
        if not isinstance(em, str) or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", em):
            rep.error(name, rel, 1, "manifest", "author.email is missing or not an email address")
    if need("license", str, "a string") and data["license"] != LICENSE_ID:
        rep.error(name, rel, 1, "manifest", "license must be %s" % LICENSE_ID)
    if need("homepage", str, "a string") and data["homepage"] != HOMEPAGE_FMT % root.name:
        rep.error(name, rel, 1, "manifest", "homepage must be %s" % (HOMEPAGE_FMT % root.name))
    if need("repository", str, "a string") and data["repository"] != REPO_URL:
        rep.error(name, rel, 1, "manifest", "repository must be %s" % REPO_URL)
    if root.name == META_PLUGIN and "keywords" not in data:
        pass  # the dependency-only plugin does not need search keywords
    elif need("keywords", list, "a list"):
        if not data["keywords"] or not all(isinstance(k, str) and k.strip() for k in data["keywords"]):
            rep.error(name, rel, 1, "manifest", "keywords must be a non-empty list of strings")

    hk = data.get("hooks")
    if isinstance(hk, str) and posixpath.normpath(hk) == "hooks/hooks.json":
        rep.warn(name, rel, 1, "manifest", "the hooks key points at hooks/hooks.json, which loads by default; remove it")

    uc = data.get("userConfig")
    if uc is not None:
        check_userconfig(name, rel, uc, rep)
    return data


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_userconfig(name, rel, uc, rep):
    if not isinstance(uc, dict):
        rep.error(name, rel, 1, "userconfig", "userConfig must be an object")
        return
    for key, ent in uc.items():
        where = "userConfig.%s" % key
        if not _CFG_KEY.match(key):
            rep.error(name, rel, 1, "userconfig", "%s: key must match [a-z][a-z0-9_]* (it becomes an env var name)" % where)
        if not isinstance(ent, dict):
            rep.error(name, rel, 1, "userconfig", "%s must be an object" % where)
            continue
        typ = ent.get("type")
        if typ not in CONFIG_TYPES:
            rep.error(name, rel, 1, "userconfig", "%s: type must be one of %s" % (where, ", ".join(CONFIG_TYPES)))
            continue
        for f in ("title", "description"):
            if not isinstance(ent.get(f), str) or not ent.get(f).strip():
                rep.error(name, rel, 1, "userconfig", "%s: missing %s" % (where, f))
        if "options" in ent:
            opts = ent["options"]
            if typ != "string":
                rep.error(name, rel, 1, "userconfig", "%s: options is only valid on string entries" % where)
            elif not isinstance(opts, list) or not opts or not all(isinstance(o, str) for o in opts):
                rep.error(name, rel, 1, "userconfig", "%s: options must be a non-empty list of strings" % where)
            elif "default" in ent and ent["default"] not in opts:
                rep.error(name, rel, 1, "userconfig", "%s: default is not one of options" % where)
        for f in ("min", "max"):
            if f in ent:
                if typ != "number":
                    rep.error(name, rel, 1, "userconfig", "%s: %s is only valid on number entries" % (where, f))
                elif not _is_num(ent[f]):
                    rep.error(name, rel, 1, "userconfig", "%s: %s must be a number" % (where, f))
        if "default" in ent:
            d = ent["default"]
            ok = True
            if typ in ("string", "directory", "file"):
                ok = isinstance(d, str)
            elif typ == "number":
                ok = _is_num(d)
            elif typ == "boolean":
                ok = isinstance(d, bool)
            if not ok:
                rep.error(name, rel, 1, "userconfig", "%s: default does not match type %s" % (where, typ))
        if "sensitive" in ent and not isinstance(ent["sensitive"], bool):
            rep.error(name, rel, 1, "userconfig", "%s: sensitive must be true or false" % where)


# ----------------------------------------------------------------------------
# The dependency-only plugin (dojo-suite)
# ----------------------------------------------------------------------------

def _dep_names(deps):
    """Dependency names from a manifest value, or None when its shape is wrong."""
    if not isinstance(deps, list):
        return None
    out = []
    for d in deps:
        if isinstance(d, str):
            out.append(d)
        elif isinstance(d, dict) and isinstance(d.get("name"), str):
            out.append(d["name"])
        else:
            return None
    return out


def _marketplace_names(path):
    """Plugin names listed in a marketplace file as (names, error). error is a short text or None."""
    raw = read_bytes(path)
    if raw is None:
        return None, "marketplace.json is unreadable"
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return None, "marketplace.json is not valid JSON"
    plugins = data.get("plugins") if isinstance(data, dict) else None
    if not isinstance(plugins, list):
        return None, "marketplace.json has no plugins list"
    return [p.get("name") for p in plugins if isinstance(p, dict)], None


def check_suite_plugin(name, root, files, manifest, rep):
    rel = ".claude-plugin/plugin.json"
    # Nothing but the manifest ships: no component folder, and no root-level settings, MCP or monitor files.
    flagged = set()
    for ab, frel in files:
        parts = frel.split("/")
        top = parts[0]
        if top == ".claude-plugin":
            if frel != rel and frel not in flagged:
                flagged.add(frel)
                rep.error(name, frel, 1, "suite-deps", "the dependency-only plugin ships only .claude-plugin/plugin.json (found %s)" % frel)
            continue
        if len(parts) == 1 and top in SUITE_ROOT_FILES:
            continue
        if top in flagged:
            continue
        flagged.add(top)
        if top in COMPONENT_DIRS and len(parts) > 1:
            rep.error(name, frel, 1, "suite-deps", "the dependency-only plugin must not ship components (found %s/)" % top)
        else:
            rep.error(name, frel, 1, "suite-deps", "the dependency-only plugin must not ship files besides plugin.json, README and LICENSE (found %s)" % (top + "/" if len(parts) > 1 else top))
    for lrel, _target in find_symlinks(root):
        top = lrel.split("/", 1)[0]
        if top not in flagged and not (top == ".claude-plugin" and lrel == rel):
            flagged.add(top)
            rep.error(name, lrel, 1, "suite-deps", "the dependency-only plugin must not ship files besides plugin.json, README and LICENSE (found %s)" % top)
    if isinstance(manifest, dict):
        for key in manifest:
            if key not in SUITE_MANIFEST_KEYS:
                rep.error(name, rel, 1, "suite-deps", "the dependency-only plugin manifest must not declare %r (allowed keys: %s)" % (key, ", ".join(SUITE_MANIFEST_KEYS)))
    if not isinstance(manifest, dict):
        return
    if "dependencies" not in manifest:
        rep.error(name, rel, 1, "suite-deps", "missing dependencies")
        return
    names = _dep_names(manifest["dependencies"])
    if names is None:
        rep.error(name, rel, 1, "suite-deps", "dependencies must be a list of plugin names")
        return
    seen = set()
    plugins_dir = root.parent
    mkt = plugins_dir.parent / ".claude-plugin" / "marketplace.json"
    listed, mkt_err = (None, None)
    have_mkt = mkt.is_file()
    if have_mkt:
        listed, mkt_err = _marketplace_names(mkt)
        if mkt_err:
            rep.error(name, rel, 1, "suite-marketplace", mkt_err)
    else:
        rep.warn(name, rel, 1, "suite-marketplace", "no .claude-plugin/marketplace.json next to plugins/; listing was not checked")
    for d in names:
        if d in seen:
            rep.error(name, rel, 1, "suite-deps", "dependency %s is listed twice" % d)
            continue
        seen.add(d)
        if d == name:
            rep.error(name, rel, 1, "suite-deps", "a plugin cannot depend on itself")
            continue
        if not re.match(r"^[a-z0-9][a-z0-9-]*$", d):
            rep.error(name, rel, 1, "suite-deps", "dependency %r must be a bare plugin name (no marketplace suffix or version)" % d)
            continue
        if not (plugins_dir / d).is_dir():
            rep.error(name, rel, 1, "suite-deps", "dependency %s has no directory under plugins/" % d)
        if d not in SUITE:
            rep.warn(name, rel, 1, "suite-deps", "dependency %s is not one of the eight suite plugins" % d)
        if listed is not None:
            n = listed.count(d)
            if n == 0:
                rep.error(name, rel, 1, "suite-marketplace", "dependency %s is not listed in marketplace.json" % d)
            elif n > 1:
                rep.error(name, rel, 1, "suite-marketplace", "dependency %s is listed %d times in marketplace.json" % (d, n))
    for m in SUITE:
        if m not in seen:
            rep.error(name, rel, 1, "suite-deps", "suite plugin %s is not a dependency" % m)


# ----------------------------------------------------------------------------
# Skills, agents, commands, output styles
# ----------------------------------------------------------------------------

def _load_md(name, root, rel, rep):
    raw = read_bytes(root / rel)
    if raw is None:
        rep.error(name, rel, 1, "frontmatter", "file is unreadable")
        return None
    fields, errors, body, body_line = parse_frontmatter(raw)
    for ln, msg in errors:
        rep.error(name, rel, ln, "frontmatter", msg)
    return fields, errors, body, raw


def _need_desc(name, rel, fields, rule, limit, rep):
    d = desc_of(fields)
    if d is None:
        if "description" not in fields.bad:
            rep.error(name, rel, 1, rule, "missing description")
        return None
    if not isinstance(d, str):
        rep.error(name, rel, fields["description"][1], rule, "description must be a string")
        return None
    if not d.strip():
        rep.error(name, rel, fields["description"][1], rule, "description is empty")
        return None
    if len(d) > limit:
        rep.error(name, rel, fields["description"][1], rule, "description is %d chars (max %d)" % (len(d), limit))
    return d


def check_skills(name, root, files, rep, budget):
    for ab, rel in files:
        parts = rel.split("/")
        if len(parts) != 3 or parts[0] != "skills" or parts[2] != "SKILL.md":
            continue
        loaded = _load_md(name, root, rel, rep)
        if loaded is None:
            continue
        fields, errors, body, raw = loaded
        skill_dir = parts[1]
        nm = fields.get("name")
        if nm is None:
            if "name" not in fields.bad:
                rep.error(name, rel, 1, "skill", "missing name")
        elif nm[0] != skill_dir:
            rep.error(name, rel, nm[1], "skill", "name %r does not match the directory name %r" % (nm[0], skill_dir))
        d = _need_desc(name, rel, fields, "skill", SKILL_DESC_MAX, rep)
        if d is not None:
            budget.append(("skill %s" % skill_dir, len(d)))
            low = d.lower()
            if not low.startswith("use when"):
                m = re.match(r"[A-Za-z][A-Za-z'-]*", d)
                ln = fields["description"][1]
                if not m:
                    rep.error(name, rel, ln, "skill", "description must start with a verb or 'Use when'")
                elif m.group(0).lower() in NON_VERB_STARTS or low.startswith("dojo"):
                    rep.error(name, rel, ln, "skill", "description must start with a verb or 'Use when' (starts with %r)" % m.group(0))
        mdl = fields.get("model")
        if mdl is not None:
            if mdl[0] not in MODEL_ALIASES:
                rep.error(name, rel, mdl[1], "skill", "model must be one of %s" % ", ".join(MODEL_ALIASES))
            elif mdl[0] != "inherit":
                rep.warn(name, rel, mdl[1], "skill", "skill model %r overrides the model for that skill's turn; keep it only on purpose" % mdl[0])
        blen = len(body.encode("utf-8"))
        if blen > SKILL_BODY_MAX:
            rep.error(name, rel, 1, "skill", "SKILL.md body is %d bytes (max %d)" % (blen, SKILL_BODY_MAX))


_TOOL_TOKEN = re.compile(r"^([A-Z][A-Za-z]+(\(.*\))?|mcp__\S+)$")
_NOT_TOOLS = frozenset(["All", "ALL", "Any", "None", "Tools"])


def _tool_tokens(value):
    if isinstance(value, list):
        return value
    items, _q = _split_flow(value)
    return [i.strip() for i in items if i.strip()]


def check_agents(name, root, files, rep, budget):
    for ab, rel in files:
        parts = rel.split("/")
        if parts[0] != "agents" or not rel.endswith(".md") or len(parts) < 2:
            continue
        loaded = _load_md(name, root, rel, rep)
        if loaded is None:
            continue
        fields, errors, body, raw = loaded
        stem = Path(rel).stem
        nm = fields.get("name")
        if nm is None:
            if "name" not in fields.bad:
                rep.error(name, rel, 1, "agent", "missing name")
        elif nm[0] != stem:
            rep.error(name, rel, nm[1], "agent", "name %r does not match the file name %r" % (nm[0], stem))
        d = _need_desc(name, rel, fields, "agent", OTHER_DESC_MAX, rep)
        if d is not None:
            budget.append(("agent %s" % stem, len(d)))
        mdl = fields.get("model")
        if mdl is None:
            if "model" not in fields.bad:
                rep.error(name, rel, 1, "agent", "missing model (an agent without one inherits the parent's model)")
        elif not isinstance(mdl[0], str) or mdl[0] not in MODEL_ALIASES:
            rep.error(name, rel, mdl[1], "agent", "model must be one of %s (case-sensitive, aliases only)" % ", ".join(MODEL_ALIASES))
        eff = fields.get("effort")
        if eff is None:
            if "effort" not in fields.bad:
                rep.error(name, rel, 1, "agent", "missing effort")
        elif not isinstance(eff[0], str) or eff[0] not in EFFORTS:
            rep.error(name, rel, eff[1], "agent", "effort must be one of %s" % ", ".join(EFFORTS))
        tl = fields.get("tools")
        if tl is None:
            if "tools" not in fields.bad:
                rep.error(name, rel, 1, "agent", "missing tools (list them explicitly)")
        else:
            toks = _tool_tokens(tl[0])
            if not toks:
                rep.error(name, rel, tl[1], "agent", "tools is empty")
            for t in toks:
                if not _TOOL_TOKEN.match(t) or t in _NOT_TOOLS:
                    rep.error(name, rel, tl[1], "agent", "bad tools entry %r (comma-separate real tool names; no wildcards)" % t)
        mt = fields.get("maxTurns")
        if mt is None:
            if "maxTurns" not in fields.bad:
                rep.error(name, rel, 1, "agent", "missing maxTurns")
        elif not (isinstance(mt[0], str) and re.match(r"^\d+$", mt[0]) and int(mt[0]) > 0):
            rep.error(name, rel, mt[1], "agent", "maxTurns must be a positive integer")


def check_commands(name, root, files, rep, budget):
    for ab, rel in files:
        parts = rel.split("/")
        if parts[0] != "commands" or not rel.endswith(".md") or len(parts) < 2:
            continue
        loaded = _load_md(name, root, rel, rep)
        if loaded is None:
            continue
        fields, errors, body, raw = loaded
        d = _need_desc(name, rel, fields, "command", OTHER_DESC_MAX, rep)
        if d is not None:
            budget.append(("command %s" % Path(rel).stem, len(d)))
        at = fields.get("allowed-tools")
        if at is None:
            if "allowed-tools" not in fields.bad:
                rep.error(name, rel, 1, "command", "missing allowed-tools")
        elif not _tool_tokens(at[0]):
            rep.error(name, rel, at[1], "command", "allowed-tools is empty")


def check_output_styles(name, root, files, rep):
    for ab, rel in files:
        parts = rel.split("/")
        if parts[0] != "output-styles" or not rel.endswith(".md") or len(parts) < 2:
            continue
        loaded = _load_md(name, root, rel, rep)
        if loaded is None:
            continue
        fields, errors, body, raw = loaded
        nm = fields.get("name")
        if nm is None or not isinstance(nm[0], str) or not nm[0].strip():
            rep.error(name, rel, 1, "outputstyle", "missing name")
        d = desc_of(fields)
        if not isinstance(d, str) or not d.strip():
            rep.error(name, rel, 1, "outputstyle", "missing description")


def check_budget(name, budget, rep):
    total = sum(n for _l, n in budget)
    if total >= BUDGET_CHARS:
        big = max(budget, key=lambda x: x[1])
        rep.error(name, "", 1, "budget", "always-on descriptions total %d chars (limit is under %d); largest: %s at %d" % (total, BUDGET_CHARS, big[0], big[1]))
    return total


# ----------------------------------------------------------------------------
# Hooks and ${CLAUDE_PLUGIN_ROOT} references
# ----------------------------------------------------------------------------

_BARE_PYTHON = re.compile(r"""(^|[\s;&|("'`])python(?![\w.])""")


def split_segments(cmd):
    segs, cur, q, i, n = [], [], None, 0, len(cmd)
    while i < n:
        c = cmd[i]
        if q:
            cur.append(c)
            if c == "\\" and q == '"' and i + 1 < n:
                cur.append(cmd[i + 1])
                i += 2
                continue
            if c == q:
                q = None
            i += 1
            continue
        if c in "\"'":
            q = c
            cur.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            cur.append(c)
            cur.append(cmd[i + 1])
            i += 2
            continue
        two = cmd[i:i + 2]
        if two in ("&&", "||"):
            segs.append("".join(cur))
            cur = []
            i += 2
            continue
        if c in ";|\n" or (c == "&" and cmd[i - 1:i] != ">" and cmd[i + 1:i + 2] != ">"):
            segs.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    if q:
        raise ValueError("unbalanced quote")
    segs.append("".join(cur))
    return segs


_ROOT_PREFIX = re.compile(r"^(?:\$\{CLAUDE_PLUGIN_ROOT\}|\$CLAUDE_PLUGIN_ROOT)(?:/|$)")
_INLINE_FLAGS = {"python3": ("-c", "-m"), "node": ("-e", "-p", "--eval", "--print"), "sh": (), "bash": ()}


_VALUE_FLAGS = {"python3": ("-W", "-X"), "node": ("-r", "--require", "--import"), "sh": ("-o", "-O"), "bash": ("-o", "-O", "--rcfile", "--init-file")}


def _script_token(head, args):
    """The script an interpreter command runs, or None for inline code, a module or no script."""
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a == "--":
            continue
        if a.startswith("-"):
            if a in _INLINE_FLAGS.get(head, ()):
                return None
            if head in ("sh", "bash") and not a.startswith("--") and "c" in a[1:]:
                return None
            if a in _VALUE_FLAGS.get(head, ()):
                skip = True
            continue
        return a
    return None


def command_problems(cmd):
    """Return a list of problem strings for one hook command line."""
    probs = []
    if _BARE_PYTHON.search(cmd):
        probs.append("bare 'python' in the command (use python3)")
    try:
        segs = split_segments(cmd)
    except ValueError:
        return probs + ["unbalanced quote in the command"]
    first = True
    for seg in segs:
        try:
            toks = shlex.split(seg)
        except ValueError:
            return probs + ["unbalanced quote in the command"]
        if not toks:
            continue
        head = toks[0]
        if first:
            if head not in INTERPRETERS:
                probs.append("command must start with %s (starts with %r)" % (", ".join(INTERPRETERS), head))
            first = False
        elif head not in INTERPRETERS and head not in BENIGN_SEGMENT_STARTS:
            probs.append("every command segment must start with %s (found %r)" % (", ".join(INTERPRETERS), head))
        if head in INTERPRETERS:
            script = _script_token(head, toks[1:])
            if script is not None and not _ROOT_PREFIX.match(script):
                probs.append("script path %r must start with ${CLAUDE_PLUGIN_ROOT}/ (hooks run from the user's project, so a relative path never finds the script)" % script)
    if first:
        probs.append("command is empty")
    return probs


_ROOT_REF = re.compile(
    r"(?:\$\{CLAUDE_PLUGIN_ROOT\}|\$CLAUDE_PLUGIN_ROOT(?![A-Za-z0-9_]))"
    r"((?:[A-Za-z0-9._/\-]|<[^>\s]*>|\*|\{[^}\s]*\})*)"
)


def check_root_refs_in_text(name, root, rel, text, rep):
    base = root.resolve()
    for ln, line in enumerate(text.splitlines(), 1):
        for m in _ROOT_REF.finditer(line):
            ref = m.group(1)
            if not ref or not ref.startswith("/"):
                continue
            ref = ref.rstrip(".,:")
            if any(ch in ref for ch in "<*{"):
                rep.error(name, rel, ln, "plugin-root", "path with a placeholder after the plugin root variable: %s" % ref)
                continue
            if ".." in ref.split("/"):
                rep.error(name, rel, ln, "plugin-root", "path leaves the plugin root: %s" % ref)
                continue
            target = base / ref.lstrip("/")
            if not os.path.exists(str(target)):
                rep.error(name, rel, ln, "plugin-root", "referenced file does not exist: %s" % ref)


_HOOK_NON_EVENT_KEYS = ("description", "modules", "hooks")


def _lint_hook_config(name, root, rel, data, rep, base, manifest_form=False):
    """Apply the hook command rules to one hook configuration: the parsed hooks.json, a hooks
    file named in plugin.json, or the inline object in plugin.json. Returns the module paths it lists.

    base is the directory that the file's "modules" paths are relative to. manifest_form
    accepts both {"hooks": {event: ...}} and a bare {event: ...} object."""
    modules_listed = []
    if not isinstance(data, dict):
        rep.error(name, rel, 1, "hook", "hook configuration must be a JSON object")
        return modules_listed
    if manifest_form and not isinstance(data.get("hooks"), dict):
        hooks = dict((k, v) for k, v in data.items() if k not in _HOOK_NON_EVENT_KEYS)
        if "hooks" in data:
            rep.error(name, rel, 1, "hook", "hooks must be an object keyed by event name")
    else:
        hooks = data.get("hooks", {})
        if not isinstance(hooks, dict):
            rep.error(name, rel, 1, "hook", "hooks must be an object keyed by event name")
            hooks = {}
        if "hooks" not in data and "modules" not in data:
            rep.error(name, rel, 1, "hook", "%s has neither hooks nor modules" % posixpath.basename(rel))
    for event, groups in hooks.items():
        if event not in COMMON_EVENTS:
            rep.warn(name, rel, 1, "hook", "event %s is outside the usual events (%s); check it against the Claude Code docs" % (event, ", ".join(COMMON_EVENTS)))
        if not isinstance(groups, list):
            rep.error(name, rel, 1, "hook", "%s: expected a list of matcher groups" % event)
            continue
        for g in groups:
            if not isinstance(g, dict) or not isinstance(g.get("hooks"), list):
                rep.error(name, rel, 1, "hook", "%s: each group needs a hooks list" % event)
                continue
            for h in g["hooks"]:
                if not isinstance(h, dict):
                    rep.error(name, rel, 1, "hook", "%s: hook entry must be an object" % event)
                    continue
                if h.get("type") != "command":
                    rep.error(name, rel, 1, "hook", "%s: hook type must be 'command' (prompt, agent and http hooks are not allowed)" % event)
                    continue
                cmd = h.get("command")
                if not isinstance(cmd, str) or not cmd.strip():
                    rep.error(name, rel, 1, "hook", "%s: command is missing" % event)
                    continue
                for p in command_problems(cmd):
                    rep.error(name, rel, 1, "hook", "%s: %s" % (event, p))
                t = h.get("timeout")
                if _is_num(t) and t > HOOK_TIMEOUT_WARN:
                    rep.warn(name, rel, 1, "hook", "%s: timeout %s is over %d seconds" % (event, t, HOOK_TIMEOUT_WARN))
    mods = data.get("modules")
    if mods is not None:
        if not isinstance(mods, list) or not all(isinstance(m, str) for m in mods):
            rep.error(name, rel, 1, "hook", "modules must be a list of paths")
        else:
            for m in mods:
                p = os.path.normpath(os.path.join(str(base), m))
                if ".." in m.split("/"):
                    rep.error(name, rel, 1, "hook", "module path leaves the plugin: %s" % m)
                elif not os.path.isfile(p):
                    rep.error(name, rel, 1, "hook", "module does not exist: %s" % m)
                modules_listed.append(p)
    return modules_listed


def _load_json_file(name, rel, path, rep):
    """(data, text) of a JSON file, or (None, None) after an error was reported."""
    raw = read_bytes(path)
    text = raw.decode("utf-8", "replace") if raw is not None else ""
    try:
        return json.loads(text.lstrip("\ufeff")), text
    except ValueError:
        rep.error(name, rel, 1, "hook", "%s is not valid JSON" % posixpath.basename(rel))
        return None, text


def check_manifest_hooks(name, root, manifest, rep):
    """Hooks declared in plugin.json (an inline object, a path, or a list of either) follow the same
    rules as hooks/hooks.json. Returns the module paths they list. hooks/hooks.json itself is
    checked by check_hooks, so a manifest entry that names it is not read twice."""
    listed = []
    if not isinstance(manifest, dict) or "hooks" not in manifest:
        return listed
    mrel = ".claude-plugin/plugin.json"
    spec = manifest["hooks"]
    entries = spec if isinstance(spec, list) else [spec]
    inline_seen = False
    for ent in entries:
        if isinstance(ent, dict):
            inline_seen = True
            listed.extend(_lint_hook_config(name, root, mrel, ent, rep, root, manifest_form=True))
        elif isinstance(ent, str):
            norm = posixpath.normpath(ent)
            if not ent.strip() or os.path.isabs(ent) or norm == ".." or norm.startswith("../") or "\\" in ent:
                rep.error(name, mrel, 1, "hook", "hooks path %r must be a relative path inside the plugin" % ent)
                continue
            if norm == "hooks/hooks.json":
                continue
            if not norm.endswith(".json"):
                rep.error(name, mrel, 1, "hook", "hooks path %r must name a .json file" % ent)
                continue
            path = root / norm
            if not path.is_file():
                rep.error(name, mrel, 1, "hook", "hooks file does not exist: %s" % ent)
                continue
            resolved = os.path.realpath(str(path))
            if not (resolved + os.sep).startswith(os.path.realpath(str(root)) + os.sep):
                rep.error(name, mrel, 1, "hook", "hooks file %r resolves outside the plugin" % ent)
                continue
            data, text = _load_json_file(name, norm, path, rep)
            if data is not None:
                listed.extend(_lint_hook_config(name, root, norm, data, rep, path.parent, manifest_form=True))
            check_root_refs_in_text(name, root, norm, text, rep)
        else:
            rep.error(name, mrel, 1, "hook", "hooks must be an inline object, a path, or a list of those")
    if inline_seen:
        text = read_text(root / ".claude-plugin" / "plugin.json")
        if text is not None:
            check_root_refs_in_text(name, root, mrel, text, rep)
    return listed


def check_hooks(name, root, files, rep, manifest=None):
    hj = root / "hooks" / "hooks.json"
    rel = "hooks/hooks.json"
    reg = root / "hooks" / "register.ts"
    modules_listed = list(check_manifest_hooks(name, root, manifest, rep))
    if hj.exists():
        data, text = _load_json_file(name, rel, hj, rep)
        if data is not None:
            modules_listed.extend(_lint_hook_config(name, root, rel, data, rep, root / "hooks"))
        check_root_refs_in_text(name, root, rel, text, rep)
    if reg.exists():
        if os.path.normpath(str(reg)) not in modules_listed:
            rep.error(name, "hooks/register.ts", 1, "hook", "register.ts exists but hooks.json does not list it in modules")
        if not hj.exists():
            rep.error(name, "hooks/register.ts", 1, "hook", "register.ts exists but there is no hooks/hooks.json")


def check_root_refs_md(name, root, files, rep):
    for ab, rel in files:
        if not rel.endswith(".md") or in_dir(rel, "tests", "evals"):
            continue
        text = read_text(ab)
        if text is not None:
            check_root_refs_in_text(name, root, rel, text, rep)


# ----------------------------------------------------------------------------
# Workflows: a small JavaScript tokenizer, then structural checks
# ----------------------------------------------------------------------------

_REGEX_PREV_KW = frozenset(["return", "typeof", "case", "in", "of", "delete", "void", "throw", "new", "else", "do", "yield", "await", "instanceof"])
_REGEX_PREV_PUNCT = frozenset("(,=:[!&|?{};+-*%<>~^")
_IDENT = re.compile(r"(?:[^\W\d]|\$)[\w$]*")
_NUMBER = re.compile(r"\d[\w.]*")


def js_tokens(src):
    """Tokens as (type, value, line). Types: ident string template tplsub tplend regex number punct.

    Comments are dropped. Template substitutions are tokenized inline between a
    tplsub and a tplend token, so calls inside them are visible.
    """
    toks = []
    n = len(src)
    i = 0
    line = 1
    depth = 0
    stack = []
    if src.startswith("#!"):
        while i < n and src[i] != "\n":
            i += 1

    def scan_tpl(j, ln):
        buf = []
        while j < n:
            c = src[j]
            if c == "\\":
                buf.append(src[j:j + 2])
                if j + 1 < n and src[j + 1] == "\n":
                    ln += 1
                j += 2
                continue
            if c == "`":
                toks.append(("template", "".join(buf), ln))
                return j + 1, ln, True
            if c == "$" and j + 1 < n and src[j + 1] == "{":
                toks.append(("template", "".join(buf), ln))
                toks.append(("tplsub", "{", ln))
                return j + 2, ln, False
            if c == "\n":
                ln += 1
            buf.append(c)
            j += 1
        toks.append(("template", "".join(buf), ln))
        return j, ln, True

    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r\f\v":
            i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            line += src.count("\n", i, j)
            i = j
            continue
        if c in "\"'":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                if src[j] == "\\":
                    j += 1
                j += 1
            toks.append(("string", src[i + 1:j], line))
            if j < n and src[j] == c:
                j += 1
            i = j
            continue
        if c == "`":
            i, line, closed = scan_tpl(i + 1, line)
            if not closed:
                depth += 1
                stack.append(depth)
            continue
        if c == "/":
            p = toks[-1] if toks else None
            is_re = (
                p is None
                or (p[0] == "punct" and p[1] in _REGEX_PREV_PUNCT)
                or p[0] == "tplsub"
                or (p[0] == "ident" and p[1] in _REGEX_PREV_KW)
            )
            if is_re:
                j, in_cls, ok = i + 1, False, False
                while j < n:
                    ch = src[j]
                    if ch == "\n":
                        break
                    if ch == "\\":
                        j += 2
                        continue
                    if ch == "[":
                        in_cls = True
                    elif ch == "]":
                        in_cls = False
                    elif ch == "/" and not in_cls:
                        ok = True
                        break
                    j += 1
                if ok:
                    j += 1
                    while j < n and src[j].isalpha():
                        j += 1
                    toks.append(("regex", src[i:j], line))
                    i = j
                    continue
            toks.append(("punct", "/", line))
            i += 1
            continue
        m = _IDENT.match(src, i)
        if m:
            toks.append(("ident", m.group(0), line))
            i = m.end()
            continue
        m = _NUMBER.match(src, i)
        if m:
            toks.append(("number", m.group(0), line))
            i = m.end()
            continue
        if src.startswith("...", i):
            toks.append(("punct", "...", line))
            i += 3
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            if stack and depth == stack[-1]:
                depth -= 1
                stack.pop()
                toks.append(("tplend", "}", line))
                i, line, closed = scan_tpl(i + 1, line)
                if not closed:
                    depth += 1
                    stack.append(depth)
                continue
            depth -= 1
        toks.append(("punct", c, line))
        i += 1
    return toks


def _is_open(t):
    return t[0] == "tplsub" or (t[0] == "punct" and t[1] in "([{")


def _is_close(t):
    return t[0] == "tplend" or (t[0] == "punct" and t[1] in ")]}")


def match_close(toks, i):
    depth = 0
    for k in range(i, len(toks)):
        if _is_open(toks[k]):
            depth += 1
        elif _is_close(toks[k]):
            depth -= 1
            if depth == 0:
                return k
    return None


def split_top(toks):
    args, cur, depth = [], [], 0
    for t in toks:
        if _is_open(t):
            depth += 1
        elif _is_close(t):
            depth -= 1
        if depth == 0 and t[0] == "punct" and t[1] == ",":
            args.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        args.append(cur)
    return args


def _is_p(t, v):
    return t[0] == "punct" and t[1] == v


def _check_agent_calls(name, rel, toks, rep):
    for idx, t in enumerate(toks):
        if t[0] != "ident" or t[1] != "agent":
            continue
        if idx + 1 >= len(toks) or not _is_p(toks[idx + 1], "("):
            continue
        prev = toks[idx - 1] if idx else None
        if prev is not None and (_is_p(prev, ".") or (prev[0] == "ident" and prev[1] == "function")):
            continue
        line = t[2]
        end = match_close(toks, idx + 1)
        if end is None:
            rep.error(name, rel, line, "workflow", "agent( call has unbalanced parentheses")
            continue
        args = split_top(toks[idx + 2:end])
        if len(args) < 2:
            rep.error(name, rel, line, "workflow", "agent() call has no options object, so model is not set")
            continue
        opts = args[1]
        if not (opts and _is_p(opts[0], "{") and match_close(opts, 0) == len(opts) - 1):
            rep.error(name, rel, line, "workflow", "agent() model is not statically visible (options is not an object literal)")
            continue
        found, spread = False, False
        for ent in split_top(opts[1:-1]):
            if not ent:
                continue
            if _is_p(ent[0], "..."):
                spread = True
                continue
            key, val = None, None
            if len(ent) >= 2 and ent[0][0] in ("ident", "string") and _is_p(ent[1], ":"):
                key, val = ent[0][1], ent[2:]
            elif len(ent) == 1 and ent[0][0] == "ident":
                key, val = ent[0][1], ent
            if key != "model":
                continue
            found = True
            if not val:
                rep.error(name, rel, line, "workflow", "agent() has an empty model value")
            elif len(val) == 1 and val[0][0] == "string" and not val[0][1].strip():
                rep.error(name, rel, line, "workflow", "agent() has model set to an empty string")
            elif len(val) == 1 and val[0][0] == "ident" and val[0][1] in ("undefined", "null"):
                rep.error(name, rel, line, "workflow", "agent() has model set to %s" % val[0][1])
        if not found:
            if spread:
                rep.error(name, rel, line, "workflow", "agent() model is not statically visible (spread options without a model key)")
            else:
                rep.error(name, rel, line, "workflow", "agent() call does not set model")


def _check_workflow_banned(name, rel, toks, rep):
    for i, t in enumerate(toks):
        if t[0] != "ident":
            continue
        nxt = toks[i + 1:i + 3]
        if t[1] == "Date" and len(nxt) == 2 and _is_p(nxt[0], ".") and nxt[1][0] == "ident" and nxt[1][1] == "now":
            rep.error(name, rel, t[2], "workflow", "Date.now is not allowed in workflow scripts")
        elif t[1] == "Math" and len(nxt) == 2 and _is_p(nxt[0], ".") and nxt[1][0] == "ident" and nxt[1][1] == "random":
            rep.error(name, rel, t[2], "workflow", "Math.random is not allowed in workflow scripts")
        elif t[1] == "new" and nxt and nxt[0][0] == "ident" and nxt[0][1] == "Date":
            after = toks[i + 2:i + 4]
            if not after or not _is_p(after[0], "("):
                rep.error(name, rel, t[2], "workflow", "new Date without arguments is not allowed in workflow scripts")
            elif len(after) > 1 and _is_p(after[1], ")"):
                rep.error(name, rel, t[2], "workflow", "new Date() without arguments is not allowed in workflow scripts")


def _check_meta(name, rel, stem, toks, rep):
    start = None
    for i in range(len(toks) - 4):
        if (toks[i][0] == "ident" and toks[i][1] == "export" and toks[i + 1][1] == "const"
                and toks[i + 2][1] == "meta" and _is_p(toks[i + 3], "=") and _is_p(toks[i + 4], "{")):
            start = i + 4
            break
    if start is None:
        rep.error(name, rel, 1, "workflow", "missing `export const meta = {...}`")
        return
    end = match_close(toks, start)
    if end is None:
        rep.error(name, rel, toks[start][2], "workflow", "meta object is not closed")
        return
    inner = toks[start + 1:end]
    for k, t in enumerate(inner):
        bad = None
        if t[0] == "tplsub":
            bad = "template substitution"
        elif t[0] == "regex":
            bad = "regex literal"
        elif t[0] == "ident":
            nxt = inner[k + 1] if k + 1 < len(inner) else None
            is_key = nxt is not None and _is_p(nxt, ":")
            if t[1] not in ("true", "false", "null") and not is_key:
                bad = "identifier or call %s" % t[1]
        elif t[0] == "punct" and t[1] not in "{}[],:":
            bad = "operator %s" % t[1]
        if bad:
            rep.error(name, rel, t[2], "workflow", "meta must be a pure literal (found %s)" % bad)
            return
    top = {}
    for ent in split_top(inner):
        if len(ent) >= 2 and ent[0][0] in ("ident", "string") and _is_p(ent[1], ":"):
            top[ent[0][1]] = ent[2:]
    nm = top.get("name")
    if nm is None:
        rep.error(name, rel, toks[start][2], "workflow", "meta is missing name")
    elif len(nm) != 1 or nm[0][0] not in ("string", "template"):
        rep.error(name, rel, toks[start][2], "workflow", "meta.name must be a string literal")
    elif nm[0][1] != stem:
        rep.error(name, rel, nm[0][2], "workflow", "meta.name %r does not match the file name %r" % (nm[0][1], stem))
    ds = top.get("description")
    if ds is None or not ds or ds[0][0] not in ("string", "template"):
        rep.error(name, rel, toks[start][2], "workflow", "meta is missing description")
    ph = top.get("phases")
    if ph is None or not ph or not _is_p(ph[0], "["):
        rep.error(name, rel, toks[start][2], "workflow", "meta is missing phases (a list)")


def check_workflows(name, root, files, rep):
    for ab, rel in files:
        parts = rel.split("/")
        if parts[0] != "workflows" or not rel.endswith(".js"):
            continue
        text = read_text(ab)
        if text is None:
            rep.error(name, rel, 1, "workflow", "file is unreadable")
            continue
        toks = js_tokens(text)
        _check_agent_calls(name, rel, toks, rep)
        _check_workflow_banned(name, rel, toks, rep)
        _check_meta(name, rel, Path(rel).stem, toks, rep)


# ----------------------------------------------------------------------------
# Python 3.9 compile + PEP 604 (one subprocess for the whole run)
# ----------------------------------------------------------------------------

_CHILD = r'''
import ast, importlib, json, sys
out = []
TYPE_NAMES = set("int str float bool bytes bytearray list dict tuple set frozenset complex object type".split())
SUB_NAMES = set("list dict tuple set frozenset type".split())
# modules where a missing attribute means "newer than this Python"
API_MODULES = set(("itertools functools contextlib typing math dataclasses enum types collections statistics "
                   "operator string zipfile bisect inspect pathlib textwrap shlex tempfile hashlib secrets "
                   "heapq copy json re io").split())
NEWER_ATTRS = set([("sys", "stdlib_module_names"), ("sys", "orig_argv")])
DC_KEYS = set(["slots", "kw_only", "match_args", "weakref_slot"])
VER = "%d.%d" % (sys.version_info[0], sys.version_info[1])


def is_type_operand(n):
    if isinstance(n, ast.Constant) and n.value is None:
        return True
    if isinstance(n, ast.Name) and n.id in TYPE_NAMES:
        return True
    return isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id in SUB_NAMES


def has_member(mod, name):
    if hasattr(mod, name):
        return True
    try:
        importlib.import_module(mod.__name__ + "." + name)
        return True
    except Exception:
        return False


def bitor(node):
    for x in ast.walk(node):
        if isinstance(x, ast.BinOp) and isinstance(x.op, ast.BitOr):
            return x
    return None


def line_of(n):
    return getattr(n, "lineno", 0)


for f in sys.argv[1:]:
    try:
        with open(f, "rb") as fh:
            data = fh.read()
    except OSError as e:
        out.append([f, 0, "py39-compile", "unreadable: " + type(e).__name__])
        continue
    try:
        compile(data, f, "exec", dont_inherit=True)
    except SyntaxError as e:
        out.append([f, e.lineno or 0, "py39-compile",
                    "does not compile under Python %s: %s" % (VER, e.msg)])
        continue
    except (ValueError, RecursionError, MemoryError) as e:
        out.append([f, 0, "py39-compile", "does not compile: " + type(e).__name__])
        continue
    tree = ast.parse(data, f)
    future = False
    for n in tree.body:
        if isinstance(n, ast.ImportFrom) and n.module == "__future__":
            for a in n.names:
                if a.name == "annotations":
                    future = True
    reported = set()
    skip = set()
    for n in ast.walk(tree):
        anns = []
        if isinstance(n, ast.arg) and n.annotation is not None:
            anns.append(n.annotation)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.returns is not None:
            anns.append(n.returns)
        elif isinstance(n, ast.AnnAssign):
            anns.append(n.annotation)
        for a in anns:
            if future:
                for x in ast.walk(a):
                    skip.add(id(x))
                continue
            for x in ast.walk(a):
                if isinstance(x, ast.BinOp) and isinstance(x.op, ast.BitOr):
                    reported.add(id(x))
            b = bitor(a)
            if b is not None:
                out.append([f, line_of(b), "py39-pep604",
                            "X | Y in an annotation fails when the def runs on 3.9; add `from __future__ import annotations` or use Optional/Union"])
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in ("isinstance", "issubclass") and len(n.args) >= 2):
            b = bitor(n.args[1])
            if b is not None:
                for x in ast.walk(n.args[1]):
                    reported.add(id(x))
                out.append([f, line_of(b), "py39-pep604",
                            "X | Y in %s() fails on 3.9; pass a tuple" % n.func.id])
    for n in ast.walk(tree):
        if (isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr) and id(n) not in reported and id(n) not in skip
                and (is_type_operand(n.left) or is_type_operand(n.right))):
            out.append([f, line_of(n), "py39-pep604",
                        "X | Y between types raises TypeError at runtime on 3.9; use Optional/Union or a tuple"])
    mods = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.asname:
                    mods[a.asname] = a.name
                else:
                    mods[a.name.split(".")[0]] = a.name.split(".")[0]
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level and n.module in API_MODULES:
            try:
                m = importlib.import_module(n.module)
            except Exception:
                continue
            for a in n.names:
                if a.name != "*" and not has_member(m, a.name):
                    out.append([f, line_of(n), "py39-api",
                                "%s.%s does not exist on Python %s" % (n.module, a.name, VER)])
    guarded = set()
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("hasattr", "getattr")
                and len(n.args) >= 2 and isinstance(n.args[0], ast.Name)
                and isinstance(n.args[1], ast.Constant) and isinstance(n.args[1].value, str)):
            guarded.add((n.args[0].id, n.args[1].value))
    loaded = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in mods:
            if (n.value.id, n.attr) in guarded:
                continue
            modname = mods[n.value.id]
            if modname not in API_MODULES and (modname, n.attr) not in NEWER_ATTRS:
                continue
            if modname not in loaded:
                try:
                    loaded[modname] = importlib.import_module(modname)
                except Exception:
                    loaded[modname] = None
            m = loaded[modname]
            if m is not None and not has_member(m, n.attr):
                out.append([f, line_of(n), "py39-api",
                            "%s.%s does not exist on Python %s" % (modname, n.attr, VER)])
        elif isinstance(n, ast.Call):
            kws = set(k.arg for k in n.keywords if k.arg)
            fn = n.func
            if isinstance(fn, ast.Name) and fn.id == "zip" and "strict" in kws:
                out.append([f, line_of(n), "py39-api", "zip(strict=...) needs Python 3.10"])
            elif isinstance(fn, ast.Name) and fn.id in ("aiter", "anext"):
                out.append([f, line_of(n), "py39-api", "%s() needs Python 3.10" % fn.id])
            elif ((isinstance(fn, ast.Name) and fn.id == "dataclass")
                  or (isinstance(fn, ast.Attribute) and fn.attr == "dataclass")) and kws & DC_KEYS:
                out.append([f, line_of(n), "py39-api", "dataclass(%s=...) needs Python 3.10" % sorted(kws & DC_KEYS)[0]])
            elif isinstance(fn, ast.Attribute) and fn.attr == "bit_count":
                out.append([f, line_of(n), "py39-api", "int.bit_count() needs Python 3.10"])
print(json.dumps(out))
'''


def py39_interpreter():
    return os.environ.get("DOJO_PY39") or "/usr/bin/python3"


def run_py39(paths):
    """Returns a list of [path, line, rule, message], or None when it could not run."""
    interp = py39_interpreter()
    if not (os.path.isfile(interp) and os.access(interp, os.X_OK)):
        return None
    if not paths:
        return []
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for k in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
        env.pop(k, None)
    try:
        r = subprocess.run([interp, "-c", _CHILD] + list(paths), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env=env, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout.decode("utf-8"))
    except ValueError:
        return None


# ----------------------------------------------------------------------------
# Generic leak scan and voice scan. Names of private projects, people and tools
# are not listed here: suite_denylist.py reads them from local-only files.
# ----------------------------------------------------------------------------

# Names that read as obviously synthetic, so a fixture path such as /home/tester/proj is not a leak.
_PLACEHOLDER_HOMES = (r"(?:user|username|you|yourname|your-name|name|me|example|runner|shared|public|default|"
                      r"tester|test|testuser|someone|alice|bob|dev|ubuntu|ci)")

INTERNAL_PATTERNS = [
    ("absolute home directory", re.compile(
        r"(?<![\w.~$-])/(?:Users|home)/(?!(?i:" + _PLACEHOLDER_HOMES + r")(?![A-Za-z0-9._-]))[A-Za-z0-9._-]+")),
    ("absolute home directory (Windows)", re.compile(
        r"(?i)\b[a-z]:[\\/]Users[\\/](?!" + _PLACEHOLDER_HOMES + r"(?![A-Za-z0-9._-]))[A-Za-z0-9._-]+")),
]

VOICE_PATTERNS = [re.compile(p, re.I) for p in (
    r"\becosystems?\b",
    r"(?<![\w.])platforms?\b",
    r"\boptimi[sz]\w*",
    r"\bleverag\w*",
    r"\bpowerful\b",
    r"\bsupercharg\w*",
    r"\bseamless(?:ly)?\b",
    r"works out of the box",
    r"\bcheap(?:er)?\b",
    r"\bsav(?:e|es|ing|ings)\b[^.\n]{0,20}\d+\s*%",
    r"\d+\s*%\s*(?:fewer|less|lower|cheaper|savings?)",
    r"\b\d+(?:\.\d+)?\s*[x\u00d7]\s+(?:faster|cheaper|fewer|less|smaller|lower)\b",
    r"\bhalf the (?:tokens|cost|price|spend)\b",
)]


def check_internal_refs(name, files, rep):
    for ab, rel in files:
        if "__pycache__" in rel.split("/") or rel.endswith(".pyc"):
            continue
        text = read_text(ab)
        if text is None:
            continue
        for ln, line in enumerate(text.splitlines(), 1):
            for label, rx in INTERNAL_PATTERNS:
                if rx.search(line):
                    rep.error(name, rel, ln, "internal-ref", "machine-specific path (%s); use a placeholder or a relative path" % label)


_ABS_TARGET = re.compile(r"^(?:/|\\\\|[A-Za-z]:[\\/])")


def check_symlinks(name, root, rep):
    """A symlink's target string is the text git stores for it, so it gets the same leak scan as file contents.
    The link's own path is scanned too, as if it were rooted at /, so a copied home path used as
    a directory layout is caught. suite_denylist.py checks names against the local lists."""
    for rel, target in find_symlinks(root):
        for label, rx in INTERNAL_PATTERNS:
            if rx.search("/" + rel):
                rep.error(name, rel, 1, "internal-ref", "machine-specific path in a symlink name (%s); rename the link" % label)
            if rx.search(target):
                rep.error(name, rel, 1, "internal-ref", "machine-specific path in a symlink target (%s); use a placeholder or a relative path" % label)
        if not target:
            rep.error(name, rel, 1, "symlink", "symlink target could not be read")
            continue
        if _ABS_TARGET.match(target):
            rep.error(name, rel, 1, "symlink", "symlink has an absolute target; a plugin install copies the plugin, so only relative links inside it can work")
            continue
        joined = posixpath.normpath(posixpath.join(posixpath.dirname(rel), target.replace("\\", "/")))
        if joined == ".." or joined.startswith("../"):
            rep.error(name, rel, 1, "symlink", "symlink target leaves the plugin")
        elif not os.path.exists(str(root / rel)):
            rep.error(name, rel, 1, "symlink", "symlink target does not exist")


def check_voice(name, root, files, manifest, rep):
    def scan(rel, text):
        for ln, line in enumerate(text.splitlines(), 1):
            for rx in VOICE_PATTERNS:
                m = rx.search(line)
                if m:
                    rep.error(name, rel, ln, "voice", "banned wording: %r" % m.group(0))

    for ab, rel in files:
        if not rel.endswith(".md") or in_dir(rel, "tests", "evals", "node_modules"):
            continue
        text = read_text(ab)
        if text is not None:
            scan(rel, text)
    if isinstance(manifest, dict):
        bits = [manifest.get("description")]
        kw = manifest.get("keywords")
        if isinstance(kw, list):
            bits.extend(kw)
        scan(".claude-plugin/plugin.json", "\n".join(b for b in bits if isinstance(b, str)))


# ----------------------------------------------------------------------------
# Mechanism rules
# ----------------------------------------------------------------------------

_NET_MODULES = ("urllib.request", "http.client", "socket", "requests", "httpx", "ftplib", "smtplib")
_DYNAMIC_IMPORT = re.compile(r"(?<![\w.])__import__\s*\(")


def _net_hit(mod):
    return any(mod == m or mod.startswith(m + ".") for m in _NET_MODULES)


def _code_strings(text):
    """String constants in a Python file that are not docstrings; None when it does not parse."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return None
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docs.add(id(body[0].value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            out.append(node.value)
    return out


def check_mechanism(name, root, files, manifest, rep, kill_switch=True):
    short = name[len("dojo-"):] if name.startswith("dojo-") else name
    env_name = "DOJO_" + short.upper().replace("-", "_") + "_OFF"
    hook_py = [(ab, rel) for ab, rel in files if rel.startswith("hooks/") and rel.endswith(".py")]
    if hook_py:
        strings = []
        for ab, rel in hook_py:
            text = read_text(ab) or ""
            cs = _code_strings(text)
            if cs is None:
                cs = [text]  # does not parse: py39-compile reports it; fall back to a plain text search
            strings.extend(cs)
            for ln, line in enumerate(text.splitlines(), 1):
                m = re.match(r"^\s*import\s+(.+)$", line)
                mods = []
                if m:
                    mods = [p.strip().split(" as ")[0].split()[0] for p in m.group(1).split(",") if p.strip()]
                m2 = re.match(r"^\s*from\s+([\w.]+)\s+import\s+(.+)$", line)
                if m2:
                    mods = [m2.group(1)]
                    if m2.group(1) == "urllib" and re.search(r"\brequest\b", m2.group(2)):
                        mods.append("urllib.request")
                    if m2.group(1) == "http" and re.search(r"\bclient\b", m2.group(2)):
                        mods.append("http.client")
                if any(_net_hit(x) for x in mods):
                    rep.error(name, rel, ln, "hook-no-network", "hook scripts must not use the network")
                if not line.lstrip().startswith("#") and _DYNAMIC_IMPORT.search(line):
                    rep.error(name, rel, ln, "hook-no-network", "__import__ hides what a hook loads; import modules by name")
        if kill_switch:
            for needle in ("DOJO_OFF", env_name):
                if not any(needle in c for c in strings):
                    rep.error(name, "hooks", 1, "kill-switch", "no hook script reads %s (a comment or docstring does not count)" % needle)
    if (root / "hooks" / "register.ts").exists():
        uc = manifest.get("userConfig") if isinstance(manifest, dict) else None
        has_bool = isinstance(uc, dict) and any(isinstance(e, dict) and e.get("type") == "boolean" for e in uc.values())
        if not has_bool:
            rep.error(name, ".claude-plugin/plugin.json", 1, "mod", "a plugin with hooks/register.ts needs a boolean userConfig entry to switch the mod off")
    for ab, rel in files:
        parts = rel.split("/")
        if "__pycache__" in parts or rel.endswith(".pyc") or parts[-1] == ".DS_Store":
            rep.error(name, rel, 1, "junk", "build or system file inside the plugin")
    evals = root / "evals"
    if evals.is_dir():
        for d in sorted(os.listdir(str(evals))):
            p = evals / d
            if p.is_dir():
                cy = p / "case.yaml"
                if not cy.is_file() or cy.stat().st_size == 0:
                    rep.error(name, "evals/%s" % d, 1, "evals", "case.yaml is missing or empty")


# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------

def lint_plugin(root, rep, skips, py_files, stats):
    name = root.name
    files = walk_plugin(root)
    stats["files"] += len(files)
    manifest = check_manifest(name, root, rep)
    meta = name == META_PLUGIN
    budget = []
    check_skills(name, root, files, rep, budget)
    check_agents(name, root, files, rep, budget)
    check_commands(name, root, files, rep, budget)
    check_output_styles(name, root, files, rep)
    if not meta:  # the dependency-only plugin adds no always-on text, so there is nothing to budget
        total = check_budget(name, budget, rep)
        stats["budget_chars"] += total
    check_hooks(name, root, files, rep, manifest)
    check_root_refs_md(name, root, files, rep)
    check_workflows(name, root, files, rep)
    check_internal_refs(name, files, rep)
    check_symlinks(name, root, rep)
    check_voice(name, root, files, manifest, rep)
    check_mechanism(name, root, files, manifest, rep, kill_switch=not meta)
    if meta:
        check_suite_plugin(name, root, files, manifest, rep)
    for ab, rel in files:
        if rel.endswith(".py") and "__pycache__" not in rel.split("/"):
            py_files.append((name, ab, rel))


def build_parser():
    ap = argparse.ArgumentParser(
        prog="suite_lint.py",
        description="Structural linter for the Dojo suite plugins. Exit 0 clean, 1 defects, 2 could not run. "
                    "Warnings never change the exit code.",
    )
    ap.add_argument("targets", nargs="*", help="plugin names or directories (default: the eight suite plugins and dojo-suite)")
    ap.add_argument("--json", action="store_true", help="print one JSON document instead of text")
    ap.add_argument("--skip", default="", help="comma-separated rule ids to skip (a prefix such as py39 skips py39-*)")
    ap.add_argument("--repo", default=None, help="repo root that holds plugins/ (default: the parent of this script's directory)")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    skips = [s.strip() for s in args.skip.split(",") if s.strip()]
    repo = Path(args.repo).resolve() if args.repo else Path(__file__).resolve().parent.parent
    plugins_dir = repo / "plugins"
    notes = []
    rep = Report()
    roots = []

    if args.targets:
        for t in args.targets:
            cand = None
            if os.sep not in t and (plugins_dir / t).is_dir():
                cand = plugins_dir / t
            elif Path(t).is_dir():
                cand = Path(t).resolve()
            if cand is None:
                print("suite-lint: no such plugin: %s" % t, file=sys.stderr)
                return 2
            roots.append(cand)
    else:
        if not plugins_dir.is_dir():
            print("suite-lint: could not run: no plugins directory under the repo", file=sys.stderr)
            return 2
        present = 0
        for nm in LINTED_BY_DEFAULT:
            if (plugins_dir / nm).is_dir():
                roots.append(plugins_dir / nm)
                present += 1
            else:
                rep.error(nm, "", 1, "plugin", "suite plugin not found under plugins/")
        if present == 0:
            print("suite-lint: could not run: none of the suite plugins exist under plugins/", file=sys.stderr)
            return 2
        for d in sorted(os.listdir(str(plugins_dir))):
            if d.startswith("dojo-") and d not in LINTED_BY_DEFAULT and (plugins_dir / d).is_dir():
                notes.append("%s is not a suite plugin, not linted" % d)

    if not rule_skipped("py39-compile", skips) or not rule_skipped("py39-pep604", skips):
        interp = py39_interpreter()
        if not (os.path.isfile(interp) and os.access(interp, os.X_OK)):
            print("suite-lint: could not run: Python 3.9 interpreter not found (set DOJO_PY39)", file=sys.stderr)
            return 2

    stats = {"files": 0, "budget_chars": 0}
    py_files = []
    for r in roots:
        lint_plugin(r, rep, skips, py_files, stats)

    if py_files and (not rule_skipped("py39-compile", skips) or not rule_skipped("py39-pep604", skips)):
        res = run_py39([ab for _n, ab, _r in py_files])
        if res is None:
            print("suite-lint: could not run: the Python 3.9 check failed to execute", file=sys.stderr)
            return 2
        lookup = dict((ab, (n, rl)) for n, ab, rl in py_files)
        for path, line, rule, msg in res:
            n, rl = lookup.get(path, ("?", path))
            rep.error(n, rl, line, rule, msg)

    if stats["budget_chars"] // 4 >= SUITE_TOKEN_WARN:
        rep.warn("suite", "", 1, "budget", "suite-wide always-on descriptions are about %d tokens (target is under %d)" % (stats["budget_chars"] // 4, SUITE_TOKEN_WARN))

    items = [it for it in rep.items if not rule_skipped(it[3], skips)]
    items.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[5]))
    errors = [it for it in items if it[4] == ERROR]
    warns = [it for it in items if it[4] == WARN]

    if args.json:
        doc = {
            "plugins": [r.name for r in roots],
            "files": stats["files"],
            "errors": len(errors),
            "warnings": len(warns),
            "notes": notes,
            "findings": [
                {"plugin": p, "file": rl, "line": ln, "rule": ru, "severity": sv, "message": ms}
                for p, rl, ln, ru, sv, ms in items
            ],
            "exit": 1 if errors else 0,
        }
        print(json.dumps(doc, indent=2))
    else:
        for note in notes:
            print("note: %s" % note)
        for p, rl, ln, ru, sv, ms in items:
            where = "%s/%s" % (p, rl) if rl else p
            print("%s:%d:%s: %s%s" % (where, ln, ru, "warning: " if sv == WARN else "", ms))
        print("suite-lint: %d plugin(s), %d file(s), %d error(s), %d warning(s)" % (len(roots), stats["files"], len(errors), len(warns)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
