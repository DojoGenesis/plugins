"""Static checks (manifests, skill, copy rules, parity of the shared tables) and the shared case table."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

import _helpers as h

ROOT = h.PLUGIN_ROOT
PROMISE = '"Done" means a check ran and passed in this session. Flags claims of success with no evidence behind them.'


def read(*parts):
    with open(os.path.join(ROOT, *parts), "r") as fh:
        return fh.read()


def load_json(*parts):
    return json.loads(read(*parts))


def public_files():
    """Every file the plugin ships, except bytecode caches."""
    out = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            out.append(os.path.join(base, f))
    return sorted(out)


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.m = load_json(".claude-plugin", "plugin.json")

    def test_required_fields(self):
        m = self.m
        self.assertEqual(m["name"], "dojo-verify")
        self.assertRegex(m["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(m["version"], "0.1.0")
        self.assertEqual(m["author"], {"name": "Dojo Genesis", "email": "cruz@trespiesdesign.com"})
        self.assertEqual(m["homepage"], "https://dojogenesis.com/suite#dojo-verify")
        self.assertEqual(m["repository"], "https://github.com/DojoGenesis/plugins")
        self.assertEqual(m["license"], "Apache-2.0")
        self.assertTrue(isinstance(m["keywords"], list) and m["keywords"])

    def test_description_is_the_promise_verbatim(self):
        self.assertEqual(self.m["description"], PROMISE)
        self.assertLessEqual(len(self.m["description"]), 200)

    def test_every_user_config_field_has_a_default_and_a_valid_type(self):
        cfg = self.m["userConfig"]
        self.assertEqual(sorted(cfg), ["mode", "show_status", "toast_unverified"])
        for key, field in cfg.items():
            self.assertIn("default", field, key)
            self.assertIn(field["type"], ("string", "number", "boolean", "directory", "file"), key)
            self.assertTrue(field["title"] and field["description"], key)
        self.assertEqual(cfg["mode"]["default"], "block")
        self.assertEqual(cfg["mode"]["options"], ["block", "warn", "off"])
        self.assertIn(cfg["mode"]["default"], cfg["mode"]["options"])
        self.assertIs(cfg["show_status"]["default"], True)
        self.assertIs(cfg["toast_unverified"]["default"], True)


class TestHooksJson(unittest.TestCase):
    def setUp(self):
        self.hooks = load_json("hooks", "hooks.json")

    def test_only_the_stop_event_is_registered(self):
        self.assertEqual(list(self.hooks["hooks"]), ["Stop"])

    def test_commands_use_python3_and_the_files_exist(self):
        seen = 0
        for group in self.hooks["hooks"]["Stop"]:
            for hook in group["hooks"]:
                seen += 1
                self.assertEqual(hook["type"], "command")
                self.assertTrue(hook["command"].startswith('python3 "${CLAUDE_PLUGIN_ROOT}/'), hook["command"])
                path = re.search(r'\$\{CLAUDE_PLUGIN_ROOT\}/([^"]+)', hook["command"]).group(1)
                self.assertTrue(os.path.isfile(os.path.join(ROOT, path)), path)
                self.assertIsInstance(hook["timeout"], int)
                self.assertTrue(1 <= hook["timeout"] <= 30)
        self.assertEqual(seen, 1)

    def test_the_module_is_listed(self):
        self.assertEqual(self.hooks["modules"], ["./register.ts"])
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "hooks", "register.ts")))
        self.assertTrue(self.hooks["description"])


class TestSkill(unittest.TestCase):
    def setUp(self):
        text = read("skills", "evidence", "SKILL.md")
        _, front, body = text.split("---\n", 2)
        self.front = dict(re.findall(r"^(\w+): (.*)$", front, re.M))
        self.body = body

    def test_frontmatter(self):
        self.assertEqual(self.front["name"], "evidence")
        desc = self.front["description"]
        self.assertTrue(desc.startswith("Use when"))
        self.assertLessEqual(len(desc), 250)

    def test_body_budget(self):
        self.assertLessEqual(len(self.body.encode("utf-8")), 6 * 1024)

    def test_it_points_at_the_protocol_by_name_and_the_reference_by_plugin_root(self):
        self.assertIn("the Dojo Protocol, rules 5, 6 and 9", self.body)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/skills/evidence/rules.md", self.body)
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "skills", "evidence", "rules.md")))

    def test_always_on_description_budget(self):
        total = len(self.front["description"])
        self.assertLess(total, 1000)

    def test_the_six_rules_are_present(self):
        for phrase in ("A report is a claim", "Load the real page", "Empty output is not evidence",
                       "cannot catch its own bug", "Count returns, not dispatches", "A hash beats a version"):
            self.assertIn(phrase, self.body)


class TestCopyRules(unittest.TestCase):
    # Only the public vocabulary rule is checked here; the suite's own lint scripts cover everything else.
    BANNED = [
        r"\becosystem\b", r"\bplatform\b", r"\boptimi[sz]e", r"\bleverag", r"\bpowerful\b", r"\bsupercharge",
        r"\bseamless", r"\bcheap", r"out of the box", r"\d\s*%", r"\bsave[sd]?\s+\d",
    ]

    def texts(self):
        """The plugin's public copy: README, manifest, hooks manifest, skills and eval scaffolds."""
        for path in public_files():
            rel = os.path.relpath(path, ROOT)
            if not (rel in ("README.md", ".claude-plugin/plugin.json", "hooks/hooks.json")
                    or rel.startswith("skills/") or rel.startswith("evals/")):
                continue
            try:
                with open(path, "r") as fh:
                    yield rel, fh.read()
            except UnicodeDecodeError:
                continue

    def test_banned_words_and_numbers_are_absent_from_public_copy(self):
        for rel, text in self.texts():
            for pattern in self.BANNED:
                m = re.search(pattern, text, re.I)
                self.assertIsNone(m, "%s matches %s" % (rel, pattern))

    def test_readme_has_the_required_parts(self):
        text = read("README.md")
        self.assertIn(PROMISE, text)
        self.assertIn("/plugin install dojo-verify@dojo-genesis", text)
        self.assertIn("CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1", text)
        self.assertIn("DOJO_OFF=1", text)
        self.assertIn("DOJO_VERIFY_OFF=1", text)
        self.assertIn("Tested with Claude Code 2.1.286", text)
        self.assertIn("early access", text.lower())
        self.assertIn("Honest limits", text)

    def test_eval_scaffolds_exist_and_parse(self):
        for name in ("claim-needs-check", "unverified-disclosed"):
            text = read("evals", name, "case.yaml")
            case = json.loads(text[text.index("{"):])
            self.assertEqual(case["name"], name)
            self.assertEqual(case["schema_version"], "1.0")
            self.assertIn("graders", case)
            self.assertIn("Not run by the build", text)


class TestParity(unittest.TestCase):
    def extract(self, rel, label):
        text = read(*rel.split("/"))
        m = re.search(r"// BEGIN %s\n(.*?)\n// END %s\n" % (re.escape(label), re.escape(label)), text, re.S)
        self.assertIsNotNone(m, rel)
        return json.loads(m.group(1))

    def test_patterns_ts_equals_patterns_json(self):
        self.assertEqual(self.extract("hooks/patterns.ts", "patterns.json"), load_json("hooks", "patterns.json"))

    def test_cases_ts_equals_cases_json(self):
        self.assertEqual(self.extract("tests/cases.ts", "cases.json"), load_json("tests", "cases.json"))

    def test_sync_script_reports_nothing_to_do(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "sync_patterns.py"), "--check"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(r.returncode, 0, r.stdout.decode())

    def test_patterns_use_only_the_regex_subset_python_and_javascript_share(self):
        raw = load_json("hooks", "patterns.json")
        bodies = list(raw["strong"]) + list(raw["weak"]) + list(raw["disclosure"]) + list(raw["disclosure_frames"]) + [
            raw["failure_markers"], raw["check"]["script_pattern"], raw["check"]["task_pattern"],
            raw["check"]["python_re"], raw["check"]["errexit_re"], raw["check"]["script_name_re"],
            raw["claim_edges"]["before"],
            raw["claim_edges"]["after"],
            raw["clause_break"], raw["mutate"]["refused_markers"], raw["mutate"]["not_found_re"],
            raw["mutate"]["interp_write_re"],
            raw["check"]["script_dir_name_re"],
        ] + list(raw["history"].values()) + list(raw["question"].values())
        for body in bodies:
            self.assertNotIn("(?P<", body)
            self.assertNotRegex(body, r"\(\?[aiLmsux]+[:)]")  # no inline flags
            self.assertNotIn("\\Z", body)
            self.assertNotIn("\\A", body)
            self.assertNotIn("(?>", body)
            re.compile(body)  # still valid in Python


class TestSharedCaseTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hook = h.load_hook_module()
        cls.cases = load_json("tests", "cases.json")

    def test_command_cases(self):
        wrong = []
        for c in self.cases["commands"]:
            if self.hook.is_evidence(c["cmd"], c["output"]) is not c["evidence"]:
                wrong.append((c["cmd"], c["output"][:30], c["evidence"]))
        self.assertEqual(wrong, [])

    def test_claim_cases(self):
        wrong = []
        for c in self.cases["claims"]:
            got = self.hook.detect_claim(c["text"], c["mutated"]) is not None
            if got is not c["claim"]:
                wrong.append((c["text"], c["mutated"], c["claim"]))
        self.assertEqual(wrong, [])

    def test_mutation_cases(self):
        wrong = []
        for c in self.cases["mutations"]:
            got = any(kind == "mut" for kind, _level, _phrase in self.hook.command_events(c["cmd"]))
            if got is not c["mutates"]:
                wrong.append((c["cmd"], c["mutates"]))
        self.assertEqual(wrong, [])

    def test_the_tables_are_not_trivial(self):
        self.assertGreater(len(self.cases["mutations"]), 30)
        self.assertTrue(any(c["mutates"] for c in self.cases["mutations"]))
        self.assertTrue(any(not c["mutates"] for c in self.cases["mutations"]))
        self.assertGreater(len(self.cases["commands"]), 50)
        self.assertGreater(len(self.cases["claims"]), 50)
        self.assertTrue(any(c["evidence"] for c in self.cases["commands"]))
        self.assertTrue(any(not c["evidence"] for c in self.cases["commands"]))
        self.assertTrue(any(c["claim"] for c in self.cases["claims"]))
        self.assertTrue(any(not c["claim"] for c in self.cases["claims"]))


class TestPythonCompatibility(unittest.TestCase):
    def test_every_python_file_compiles_under_the_system_python(self):
        py = "/usr/bin/python3"
        if not os.path.exists(py):
            self.skipTest("no system python3 here")
        files = [p for p in public_files() if p.endswith(".py")]
        self.assertTrue(files)
        with tempfile.TemporaryDirectory() as tmp:
            for i, path in enumerate(files):
                out = os.path.join(tmp, "c%d.pyc" % i)
                r = subprocess.run(
                    [py, "-c", "import py_compile,sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)",
                     path, out],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                self.assertEqual(r.returncode, 0, "%s: %s" % (path, r.stderr.decode()))

    def test_the_system_python_is_a_version_the_hook_supports(self):
        py = "/usr/bin/python3"
        if not os.path.exists(py):
            self.skipTest("no system python3 here")
        r = subprocess.run([py, "-c", "import sys; print(sys.version_info[:2] >= (3, 9))"], stdout=subprocess.PIPE)
        self.assertEqual(r.stdout.decode().strip(), "True")

    def test_the_hook_source_avoids_syntax_newer_than_3_9(self):
        src = read("hooks", "stop_evidence.py")
        self.assertNotRegex(src, r"^\s*match\s+\w+.*:\s*$", "match statement")
        self.assertNotIn(".removeprefix(", src)
        self.assertNotIn(".removesuffix(", src)
        self.assertNotRegex(src, r"strict\s*=\s*True")
        self.assertNotRegex(src, r"f['\"][^'\"]*\{[^}]*=\}")


if __name__ == "__main__":
    unittest.main()
