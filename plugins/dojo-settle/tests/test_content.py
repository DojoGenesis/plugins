"""Static checks on what dojo-settle ships: manifest, skills, templates, README, eval scaffolds.

Run: cd plugins/dojo-settle && python3 -m unittest discover -s tests -v

Stdlib only. The eval-case checker below is a strict key whitelist, because
`claude plugin validate` does not read case.yaml at all.
"""
import importlib.util
import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
THIS_FILE = os.path.abspath(__file__)

PROMISE = "Settle claims with evidence: pre-registered experiments, with/without baselines and decision gates before anything becomes a number."
MARKER = "MEASUREMENTS BEGIN BELOW THIS LINE"

CATEGORIES = {
    "scout-position", "specify-commission", "dispatch-coordinate", "remember-continue", "seed-lifecycle",
    "system-prompt-intel", "repo-docs-health", "agent-telemetry", "learn-research", "understand-codebase",
    "forge", "govern-publish",
}
VERBS = {
    "use", "frame", "write", "run", "find", "check", "turn", "settle", "read", "scaffold", "measure",
    "compare", "decide", "test", "review", "build", "make", "pick", "plan", "list", "show",
}

BANNED_WORDS = [
    r"ecosystem", r"platform", r"optimi[sz]\w*", r"leverag\w*", r"powerful", r"supercharg\w*", r"seamless\w*",
    r"works out of the box", r"\bcheap\w*", r"save \d+ ?%", r"\boperator\b",
]
NUMBER_PATTERNS = [r"\d+ ?%", r"\b\d+ of \d+\b"]


def read(*parts):
    with open(os.path.join(PLUGIN, *parts), "r", encoding="utf-8") as f:
        return f.read()


def shipped_files():
    for root, dirs, files in os.walk(PLUGIN):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "results")]
        for name in files:
            p = os.path.join(root, name)
            if os.path.abspath(p) == THIS_FILE or name.endswith(".pyc") or name.endswith(".sha256"):
                continue
            yield p


def split_frontmatter(text):
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("no frontmatter")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm = {}
            for ln in lines[1:i]:
                if not ln.strip():
                    continue
                m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", ln)
                if not m:
                    raise ValueError("bad frontmatter line: " + ln)
                v = m.group(2).strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                fm[m.group(1)] = v
            return fm, "\n".join(lines[i + 1:])
    raise ValueError("unterminated frontmatter")


# ----------------------------------------------------------------------------
# minimal YAML subset reader (block maps, block lists, flow lists/maps, | scalars)
# ----------------------------------------------------------------------------

KEY_RX = re.compile(r"^([A-Za-z_][\w-]*):(?:[ \t]+(.*))?$")


def _skip(lines, i):
    while i < len(lines) and (not lines[i].strip() or lines[i].lstrip().startswith("#")):
        i += 1
    return i


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _scalar(s):
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [_scalar(x) for x in inner.split(",")] if inner else []
    if s.startswith("{") and s.endswith("}"):
        out = {}
        inner = s[1:-1].strip()
        for part in (inner.split(",") if inner else []):
            k, _, v = part.partition(":")
            out[k.strip()] = _scalar(v)
        return out
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return json.loads(s)
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1].replace("''", "'")
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if s in ("null", "~", ""):
        return None
    if re.match(r"^-?\d+$", s):
        return int(s)
    if re.match(r"^-?\d+\.\d+$", s):
        return float(s)
    return s


def _node(lines, i, indent):
    i = _skip(lines, i)
    if i >= len(lines) or _indent(lines[i]) < indent:
        return None, i
    ind = _indent(lines[i])
    if lines[i].lstrip().startswith("- ") or lines[i].strip() == "-":
        return _list(lines, i, ind)
    return _map(lines, i, ind)


def _map(lines, i, ind):
    out = {}
    while True:
        i = _skip(lines, i)
        if i >= len(lines):
            break
        line = lines[i]
        cur = _indent(line)
        if cur < ind or (cur == ind and line.lstrip().startswith("- ")):
            break
        if cur > ind:
            raise ValueError("unexpected indent on line %d" % (i + 1))
        m = KEY_RX.match(line.strip())
        if not m:
            raise ValueError("not a key line: line %d" % (i + 1))
        key, rest = m.group(1), m.group(2)
        if key in out:
            raise ValueError("duplicate key %r" % key)
        if rest is None:
            val, i = _node(lines, i + 1, ind + 1)
        elif rest.strip() in ("|", "|-", "|+"):
            block = []
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or _indent(lines[j]) > ind):
                block.append(lines[j])
                j += 1
            nonblank = [b for b in block if b.strip()]
            cut = min([_indent(b) for b in nonblank]) if nonblank else 0
            val = "\n".join(b[cut:] if b.strip() else "" for b in block).rstrip("\n") + "\n"
            i = j
        else:
            val = _scalar(rest)
            i += 1
        out[key] = val
    return out, i


def _list(lines, i, ind):
    out = []
    while True:
        i = _skip(lines, i)
        if i >= len(lines):
            break
        line = lines[i]
        if _indent(line) != ind or not (line.lstrip().startswith("- ") or line.strip() == "-"):
            break
        content = line.strip()[1:].strip()
        if KEY_RX.match(content):
            lines = list(lines)
            lines[i] = " " * (ind + 2) + content
            val, i = _map(lines, i, ind + 2)
            out.append(val)
        else:
            out.append(_scalar(content))
            i += 1
    return out, i


def parse_yaml(text):
    lines = text.split("\n")
    val, i = _node(lines, 0, 0)
    i = _skip(lines, i)
    if i < len(lines):
        raise ValueError("trailing content on line %d" % (i + 1))
    return val


# ----------------------------------------------------------------------------
# case.yaml schema (whitelist of keys the 2.1.286 eval schema accepts)
# ----------------------------------------------------------------------------

TOP_KEYS = {"schema_version", "name", "description", "tags", "plugins", "context", "execution", "runs", "graders",
            "expected_outcome"}
CONTEXT_KEYS = {"scaffold_script", "history_file", "add_dirs"}
EXEC_KEYS = {"prompt", "max_turns", "timeout_seconds", "model", "allowed_tools", "artifact_publish",
             "growthbook_overrides", "append_system_prompt", "env"}
COMMON_GRADER = {"type", "name", "weight", "arm"}
GRADER_KEYS = {
    "regex": {"target", "pattern", "flags", "match"},
    "tool_order": {"before", "after"},
    "tool_used": {"tool", "input_match", "min", "max"},
    "file_exists": {"path", "exists"},
    "llm": {"criteria", "focus"},
    "baseline": {"baseline_file", "criteria"},
}
GRADER_REQUIRED = {
    "regex": {"target", "pattern"},
    "tool_order": {"before", "after"},
    "tool_used": {"tool"},
    "file_exists": {"path"},
    "llm": {"criteria"},
    "baseline": {"baseline_file", "criteria"},
}
ABS_PATH_RX = re.compile(r"(^|[\s\"'(])/[A-Za-z][\w.-]*/")


def check_case(doc):
    """Return a list of error strings; empty means the case fits the whitelist."""
    errs = []
    if not isinstance(doc, dict):
        return ["top level is not a map"]
    for k in doc:
        if k not in TOP_KEYS:
            errs.append("unknown top-level key %r" % k)
    sv = doc.get("schema_version")
    if not isinstance(sv, str) or not re.match(r"^1(\.\d+)*$", sv):
        errs.append("schema_version must be a quoted string with major version 1")
    if not isinstance(doc.get("name"), str) or not doc.get("name"):
        errs.append("name is required")
    runs = doc.get("runs")
    if runs is not None and (not isinstance(runs, int) or isinstance(runs, bool) or runs < 1 or runs > 50):
        errs.append("runs must be an integer from 1 to 50")
    ctx = doc.get("context")
    if ctx is not None:
        if not isinstance(ctx, dict):
            errs.append("context must be a map")
        else:
            for k in ctx:
                if k not in CONTEXT_KEYS:
                    errs.append("unknown context key %r" % k)
    ex = doc.get("execution")
    if not isinstance(ex, dict):
        errs.append("execution is required")
    else:
        for k in ex:
            if k not in EXEC_KEYS:
                errs.append("unknown execution key %r" % k)
        prompt = ex.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            errs.append("execution.prompt is required")
        else:
            if ABS_PATH_RX.search(prompt) or "~/" in prompt:
                errs.append("execution.prompt names an absolute or home-directory path")
        mt = ex.get("max_turns")
        if mt is not None and (not isinstance(mt, int) or mt < 1 or mt > 200):
            errs.append("max_turns must be an integer up to 200")
        ts = ex.get("timeout_seconds")
        if ts is not None and (not isinstance(ts, int) or ts < 1 or ts > 3600):
            errs.append("timeout_seconds must be an integer up to 3600")
        at = ex.get("allowed_tools")
        if at is not None and (not isinstance(at, list) or not all(isinstance(x, str) for x in at)):
            errs.append("allowed_tools must be a list of names")
    graders = doc.get("graders")
    if not isinstance(graders, list) or not graders:
        errs.append("graders needs at least one entry")
        return errs
    seen = set()
    for n, g in enumerate(graders):
        where = "grader %d" % (n + 1)
        if not isinstance(g, dict):
            errs.append(where + " is not a map")
            continue
        gtype = g.get("type")
        if gtype not in GRADER_KEYS:
            errs.append("%s has unknown type %r" % (where, gtype))
            continue
        name = g.get("name")
        if not isinstance(name, str) or not name.strip():
            errs.append(where + " has no name")
        elif name in seen:
            errs.append("duplicate grader name %r" % name)
        else:
            seen.add(name)
        allowed = COMMON_GRADER | GRADER_KEYS[gtype]
        for k in g:
            if k not in allowed:
                errs.append("%s (%s) has unknown key %r" % (where, gtype, k))
        for k in GRADER_REQUIRED[gtype]:
            if k not in g:
                errs.append("%s (%s) is missing %r" % (where, gtype, k))
        if "arm" in g and g["arm"] not in ("with-only", "both"):
            errs.append("%s has arm %r, expected with-only or both" % (where, g["arm"]))
        if "weight" in g and (isinstance(g["weight"], bool) or not isinstance(g["weight"], (int, float))):
            errs.append(where + " weight must be a number")
        for key in ("target", "focus"):
            if key in g and gtype in ("regex", "llm") and not valid_target(g[key]):
                errs.append("%s (%s) has an invalid %s %r" % (where, gtype, key, g[key]))
    return errs


TARGET_ENUM = ("trace", "last_message", "files", "mock_calls")


def valid_target(value):
    """A regex target / llm focus is one of the enum words or the strict map {source: file, path: P}."""
    if isinstance(value, str):
        return value in TARGET_ENUM
    return (isinstance(value, dict) and set(value) == {"source", "path"} and value.get("source") == "file"
            and isinstance(value.get("path"), str) and bool(value["path"]))


BAD_NO_NAME = '''schema_version: "1.0"
name: bad-no-name
runs: 1
execution:
  prompt: |
    Say hello.
graders:
  - type: regex
    target: last_message
    pattern: "hello"
'''

BAD_WITH_ONLY_KEY = '''schema_version: "1.0"
name: bad-with-only
runs: 1
execution:
  prompt: |
    Say hello.
graders:
  - type: tool_used
    name: fired
    tool: Skill
    with_only: true
'''

BAD_ARM_VALUE = '''schema_version: "1.0"
name: bad-arm
execution:
  prompt: |
    Say hello.
graders:
  - type: llm
    name: judged
    criteria: Said hello.
    arm: sometimes
'''

GOOD_MINIMAL = '''schema_version: "1.0"
name: ok
execution:
  prompt: |
    Say hello.
graders:
  - type: regex
    name: says-hello
    target: last_message
    pattern: "hello"
'''


class TestCaseChecker(unittest.TestCase):
    def test_accepts_a_good_case(self):
        self.assertEqual(check_case(parse_yaml(GOOD_MINIMAL)), [])

    def test_rejects_grader_without_name(self):
        errs = check_case(parse_yaml(BAD_NO_NAME))
        self.assertTrue(any("no name" in e for e in errs), errs)

    def test_rejects_unknown_with_only_key(self):
        errs = check_case(parse_yaml(BAD_WITH_ONLY_KEY))
        self.assertTrue(any("with_only" in e for e in errs), errs)

    def test_rejects_bad_arm_value(self):
        errs = check_case(parse_yaml(BAD_ARM_VALUE))
        self.assertTrue(any("arm" in e for e in errs), errs)

    def test_rejects_other_defects(self):
        base = parse_yaml(GOOD_MINIMAL)
        for mutate, needle in [
            (lambda d: d.update(schema_version=1.0), "schema_version"),
            (lambda d: d.update(runs=51), "runs"),
            (lambda d: d["execution"].update(max_turns=201), "max_turns"),
            (lambda d: d["execution"].update(timeout_seconds=3601), "timeout_seconds"),
            (lambda d: d["execution"].update(prompt="Read /srv/data/file.txt now"), "path"),
            (lambda d: d["execution"].update(prompt="Read ~/notes.txt now"), "path"),
            (lambda d: d.update(bogus=1), "unknown top-level"),
            (lambda d: d["graders"].append(dict(d["graders"][0])), "duplicate"),
            (lambda d: d["graders"][0].update(type="semantic"), "unknown type"),
            (lambda d: d["graders"].__setitem__(0, {"type": "regex", "name": "x", "target": "last_message"}), "missing"),
            (lambda d: d["graders"].__setitem__(0, {"type": "regex", "name": "x", "pattern": "a", "target": "out/result.txt"}), "invalid target"),
            (lambda d: d["graders"].__setitem__(0, {"type": "regex", "name": "x", "pattern": "a", "target": {"path": "r.txt"}}), "invalid target"),
        ]:
            doc = json.loads(json.dumps(base))
            mutate(doc)
            errs = check_case(doc)
            self.assertTrue(any(needle in e for e in errs), (needle, errs))

    def test_parser_reads_the_shapes_the_scaffolds_use(self):
        doc = parse_yaml(
            'a: "x\\\\by"\nb: [r, w]\nc:\n  - type: t\n    before: { tool: A }\n    n: 2\nd: |\n  one\n    two\n  three\n')
        self.assertEqual(doc["a"], "x\\by")
        self.assertEqual(doc["b"], ["r", "w"])
        self.assertEqual(doc["c"], [{"type": "t", "before": {"tool": "A"}, "n": 2}])
        self.assertEqual(doc["d"], "one\n  two\nthree\n")


class TestShippedCases(unittest.TestCase):
    def case_paths(self):
        paths = [os.path.join(PLUGIN, "templates", "case.yaml")]
        evals = os.path.join(PLUGIN, "evals")
        for d in sorted(os.listdir(evals)):
            p = os.path.join(evals, d, "case.yaml")
            if os.path.isfile(p):
                paths.append(p)
        return paths

    def test_every_shipped_case_fits_the_schema(self):
        for p in self.case_paths():
            with self.subTest(case=os.path.relpath(p, PLUGIN)):
                with open(p, encoding="utf-8") as f:
                    errs = check_case(parse_yaml(f.read()))
                self.assertEqual(errs, [])

    def test_scaffolds_are_tagged_not_run(self):
        evals = os.path.join(PLUGIN, "evals")
        names = [d for d in sorted(os.listdir(evals)) if os.path.isfile(os.path.join(evals, d, "case.yaml"))]
        self.assertEqual(len(names), 2)
        for d in names:
            with open(os.path.join(evals, d, "case.yaml"), encoding="utf-8") as f:
                doc = parse_yaml(f.read())
            self.assertIn("scaffold", doc["tags"])
            self.assertIn("not-run", doc["tags"])
            self.assertEqual(doc["name"], d)

    def test_should_lose_case_checks_the_skill_and_script_stay_quiet(self):
        with open(os.path.join(PLUGIN, "evals", "protocol-should-lose", "case.yaml"), encoding="utf-8") as f:
            doc = parse_yaml(f.read())
        by_name = {g["name"]: g for g in doc["graders"]}
        skill = by_name["settle-skill-not-called"]
        self.assertEqual((skill["tool"], skill["min"], skill["max"], skill["arm"]), ("Skill", 0, 0, "both"))
        self.assertIn("dojo-settle", skill["input_match"])
        self.assertNotIn("prereg-script-not-run", by_name)
        self.assertNotIn("Bash", doc["execution"]["allowed_tools"])

    def test_delta_case_keeps_the_fired_indicator_with_only(self):
        with open(os.path.join(PLUGIN, "evals", "with-without-delta", "case.yaml"), encoding="utf-8") as f:
            doc = parse_yaml(f.read())
        fired = [g for g in doc["graders"] if g.get("arm") == "with-only"]
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0]["tool"], "Skill")
        scored = [g for g in doc["graders"] if g.get("arm") != "with-only"]
        self.assertGreaterEqual(len(scored), 2)
        self.assertEqual(doc["runs"], 3)


class TestCaseDetails(unittest.TestCase):
    def doc(self, name):
        with open(os.path.join(PLUGIN, "evals", name, "case.yaml"), encoding="utf-8") as f:
            return parse_yaml(f.read())

    def test_every_llm_grader_that_judges_order_reads_the_trace(self):
        for name in ("with-without-delta",):
            for g in self.doc(name)["graders"]:
                if g["type"] == "llm":
                    self.assertEqual(g.get("focus"), "trace", g["name"])

    def test_allowed_tools_follow_the_graders(self):
        lose = self.doc("protocol-should-lose")["execution"]["allowed_tools"]
        self.assertNotIn("Bash", lose)
        delta = self.doc("with-without-delta")["execution"]["allowed_tools"]
        for tool in ("Write", "Bash"):
            self.assertIn(tool, delta)

    def test_run_commands_carry_the_tool_grant_and_an_opus_judge(self):
        for rel in (("evals", "with-without-delta", "case.yaml"), ("templates", "case.yaml")):
            text = read(*rel)
            self.assertIn("--allow-tools", text, rel)
            self.assertIn("--judge-model opus", text, rel)


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.m = json.loads(read(".claude-plugin", "plugin.json"))

    def test_fields(self):
        m = self.m
        self.assertEqual(m["name"], "dojo-settle")
        self.assertEqual(m["version"], "0.1.0")
        self.assertEqual(m["license"], "Apache-2.0")
        self.assertEqual(m["homepage"], "https://dojogenesis.com/suite#dojo-settle")
        self.assertEqual(m["repository"], "https://github.com/DojoGenesis/plugins")
        self.assertEqual(m["author"], {"name": "Dojo Genesis", "email": "cruz@trespiesdesign.com"})
        self.assertTrue(m["keywords"])

    def test_description_is_the_promise_and_short_enough(self):
        self.assertEqual(self.m["description"], PROMISE)
        self.assertLessEqual(len(self.m["description"]), 200)

    def test_no_hooks_userconfig_or_experimental_key(self):
        for k in ("hooks", "userConfig", "experimental"):
            self.assertNotIn(k, self.m)
        self.assertFalse(os.path.exists(os.path.join(PLUGIN, "hooks")))
        self.assertFalse(os.path.exists(os.path.join(PLUGIN, "agents")))
        self.assertFalse(os.path.exists(os.path.join(PLUGIN, "commands")))

    def test_readme_carries_the_promise_verbatim(self):
        self.assertIn(PROMISE, read("README.md"))


class TestSkills(unittest.TestCase):
    def skills(self):
        root = os.path.join(PLUGIN, "skills")
        return sorted(d for d in os.listdir(root) if os.path.isfile(os.path.join(root, d, "SKILL.md")))

    def test_the_three_skills(self):
        self.assertEqual(self.skills(), ["decision-gate", "eval-kit", "settle"])

    def test_frontmatter_and_size(self):
        total = 0
        for d in self.skills():
            with self.subTest(skill=d):
                text = read("skills", d, "SKILL.md")
                fm, body = split_frontmatter(text)
                self.assertEqual(fm["name"], d)
                self.assertIn(fm["category"], CATEGORIES)
                desc = fm["description"]
                self.assertTrue(desc.strip())
                self.assertLessEqual(len(desc), 250)
                first = desc.split()[0].lower().rstrip(",:")
                self.assertTrue(desc.startswith("Use when") or first in VERBS, desc)
                self.assertLessEqual(len(body.encode("utf-8")), 6144)
                self.assertEqual(fm.get("model"), "inherit", "skills must not pin a model")
                total += len(desc)
        self.assertLess(total, 1000)

    def test_no_unquoted_frontmatter_value_contains_colon_space(self):
        # The suite lint and PyYAML both reject this; the lenient splitter above does not.
        for d in self.skills():
            with self.subTest(skill=d):
                lines = read("skills", d, "SKILL.md").split("\n")
                end = lines[1:].index("---") + 1
                for ln in lines[1:end]:
                    value = ln.split(":", 1)[1].strip()
                    if value[:1] in ("\"", "'"):
                        continue
                    self.assertNotIn(": ", value, ln)
                    self.assertFalse(value.endswith(":"), ln)

    def test_descriptions_are_distinct_from_each_other(self):
        descs = [split_frontmatter(read("skills", d, "SKILL.md"))[0]["description"] for d in self.skills()]
        self.assertEqual(len(set(descs)), len(descs))

    def test_skill_names_do_not_collide_with_other_plugins(self):
        others = os.path.join(os.path.dirname(PLUGIN))
        for d in self.skills():
            for plugin in os.listdir(others):
                if plugin == "dojo-settle":
                    continue
                self.assertFalse(os.path.isdir(os.path.join(others, plugin, "skills", d)),
                                 "%s also exists in %s" % (d, plugin))

    def test_plugin_root_paths_exist(self):
        rx = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+)")
        files = [os.path.join(PLUGIN, "README.md")] + [os.path.join(PLUGIN, "skills", d, "SKILL.md") for d in self.skills()]
        seen = 0
        for f in files:
            with open(f, encoding="utf-8") as fh:
                for m in rx.finditer(fh.read()):
                    rel = m.group(1).rstrip(".,")
                    seen += 1
                    self.assertTrue(os.path.exists(os.path.join(PLUGIN, rel)), "%s names missing %s" % (f, rel))
        self.assertGreater(seen, 3)

    def test_decision_gate_ties_recommendation_to_evidence(self):
        text = read("skills", "decision-gate", "SKILL.md")
        self.assertIn("not yet evidenced", text)
        self.assertIn("no default yet", text)
        self.assertIn("AskUserQuestion", text)

    def test_settle_teaches_the_baseline_arm_and_names_what_freeze_checks(self):
        text = read("skills", "settle", "SKILL.md")
        self.assertIn("without arm", text)
        self.assertIn("with-minus-without", text)
        self.assertNotIn("every section is filled", text)

    def test_eval_kit_documents_the_real_regex_target_schema(self):
        text = read("skills", "eval-kit", "SKILL.md")
        self.assertIn("{source: file, path:", text)
        self.assertNotIn("or a file path", text)
        for word in ("last_message", "trace", "files", "mock_calls"):
            self.assertIn(word, text)

    def test_target_validator_accepts_enum_and_file_map_only(self):
        for ok in ("trace", "last_message", "files", "mock_calls", {"source": "file", "path": "out.txt"}):
            self.assertTrue(valid_target(ok), ok)
        for bad in ("out.txt", "", {"path": "out.txt"}, {"source": "file"}, {"source": "url", "path": "x"}, 3, None):
            self.assertFalse(valid_target(bad), bad)

    def test_eval_kit_teaches_the_pilot_gate(self):
        text = read("skills", "eval-kit", "SKILL.md")
        for needle in ("--max-cost-usd", "--no-publish", "--runs 1", "aggregate-result.json", "manifest_invalid",
                       "disabled_by_default", "will_not_load", "costUsd", "--judge-model opus", "--allow-tools", "identity_unverified", "archive_not_probed", "focus: trace", "arm: with-only",
                       "does not read case.yaml", "No eval from this suite has been run"):
            self.assertIn(needle, text)


class TestTemplates(unittest.TestCase):
    def test_prereg_marker_once_as_a_whole_line(self):
        text = read("templates", "prereg.md")
        self.assertEqual(text.split("\n").count(MARKER), 1)
        self.assertEqual(text.count(MARKER), 1, "the marker text must not appear anywhere else in the template")

    def test_placeholders_match_the_script(self):
        spec = importlib.util.spec_from_file_location("prereg", os.path.join(PLUGIN, "scripts", "prereg.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        in_template = set(re.findall(r"\{\{([^{}\n]*)\}\}", read("templates", "prereg.md")))
        self.assertEqual(in_template, {name for _dest, name in mod.PLACEHOLDERS})

    def test_required_headings_exist_in_the_template(self):
        spec = importlib.util.spec_from_file_location("prereg2", os.path.join(PLUGIN, "scripts", "prereg.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        found = set(mod.sections(read("templates", "prereg.md")))
        for key in mod.REQUIRED_SECTIONS:
            self.assertIn(key, found)


class TestReadme(unittest.TestCase):
    def count_rows(self):
        text = read("README.md")
        return {m.group(1): int(m.group(2)) for m in re.finditer(r"^\| (\w[\w ]*) \| (\d+) \|", text, re.M)}

    def test_counts_match_disk(self):
        rows = self.count_rows()
        skills = [d for d in os.listdir(os.path.join(PLUGIN, "skills"))
                  if os.path.isfile(os.path.join(PLUGIN, "skills", d, "SKILL.md"))]
        scripts = [f for f in os.listdir(os.path.join(PLUGIN, "scripts")) if f.endswith(".py")]
        templates = [f for f in os.listdir(os.path.join(PLUGIN, "templates"))]
        evals = [d for d in os.listdir(os.path.join(PLUGIN, "evals"))
                 if os.path.isfile(os.path.join(PLUGIN, "evals", d, "case.yaml"))]
        self.assertEqual(rows["Skills"], len(skills))
        self.assertEqual(rows["Scripts"], len(scripts))
        self.assertEqual(rows["Templates"], len(templates))
        self.assertEqual(rows["Eval scaffolds"], len(evals))
        for name in ("Hooks", "Agents", "Commands"):
            self.assertEqual(rows[name], 0)
            self.assertFalse(os.path.exists(os.path.join(PLUGIN, name.lower())))

    def test_states_tested_version_and_that_no_eval_ran(self):
        text = read("README.md")
        self.assertIn("Tested with Claude Code 2.1.286", text)
        self.assertIn("No eval was run", text)

    def test_kill_switch_section_claims_nothing(self):
        text = read("README.md")
        section = text.split("## Kill switches", 1)[1].split("\n## ", 1)[0]
        self.assertIn("nothing to switch off", section)


class TestPublicWording(unittest.TestCase):
    def test_banned_vocabulary_absent(self):
        rx = re.compile("|".join(BANNED_WORDS), re.I)
        for p in shipped_files():
            with open(p, "rb") as f:
                data = f.read()
            if b"\0" in data[:4096]:
                continue
            for n, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
                self.assertIsNone(rx.search(line), "%s:%d" % (os.path.relpath(p, PLUGIN), n))

    def test_no_figures_in_public_text(self):
        rx = re.compile("|".join(NUMBER_PATTERNS))
        for p in shipped_files():
            if not p.endswith((".md", ".json")) or os.sep + "tests" + os.sep in p:
                continue
            with open(p, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    self.assertIsNone(rx.search(line), "%s:%d" % (os.path.relpath(p, PLUGIN), n))


if __name__ == "__main__":
    unittest.main()
