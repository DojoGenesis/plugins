"""Static checks on the plugin as shipped: manifest, hook wiring, skill budget, public wording."""
import glob
import json
import os
import py_compile
import re
import tempfile
import unittest

from _helpers import PLUGIN_ROOT

# The promise as the suite contract words it. plugin.json must carry it verbatim.
PROMISE = (
    "No subagent silently inherits your most expensive model. "
    "Warns or blocks unpinned dispatches; the mod routes them by role."
)


def read(*parts):
    with open(os.path.join(PLUGIN_ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def frontmatter(text):
    lines = text.splitlines()
    assert lines[0] == "---"
    meta = {}
    for line in lines[1:]:
        if line == "---":
            break
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta


class Manifest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(read(".claude-plugin", "plugin.json"))

    def test_description_is_the_promise_verbatim_and_within_budget(self):
        self.assertEqual(self.manifest["description"], PROMISE)
        self.assertLessEqual(len(self.manifest["description"]), 200)

    def test_required_fields(self):
        m = self.manifest
        self.assertEqual(m["name"], "dojo-router")
        self.assertEqual(m["version"], "0.1.0")
        self.assertEqual(m["author"], {"name": "Dojo Genesis", "email": "cruz@trespiesdesign.com"})
        self.assertEqual(m["homepage"], "https://dojogenesis.com/suite#dojo-router")
        self.assertEqual(m["repository"], "https://github.com/DojoGenesis/plugins")
        self.assertEqual(m["license"], "Apache-2.0")
        self.assertTrue(m["keywords"])

    def test_user_config_matches_the_contract(self):
        cfg = self.manifest["userConfig"]
        self.assertEqual(set(cfg), {"mode", "default_tier", "explore_tier", "auto_route", "opus_cap"})
        self.assertEqual((cfg["mode"]["options"], cfg["mode"]["default"]), (["warn", "block", "off"], "warn"))
        self.assertEqual((cfg["default_tier"]["options"], cfg["default_tier"]["default"]),
                         (["haiku", "sonnet", "opus"], "sonnet"))
        self.assertEqual((cfg["explore_tier"]["options"], cfg["explore_tier"]["default"]),
                         (["haiku", "sonnet", "opus"], "haiku"))
        self.assertEqual((cfg["auto_route"]["type"], cfg["auto_route"]["default"]), ("boolean", True))
        self.assertEqual((cfg["opus_cap"]["type"], cfg["opus_cap"]["default"]), ("number", 0))

    def test_defaults_in_the_manifest_match_the_defaults_in_the_hooks(self):
        import router_common as rc
        cfg = self.manifest["userConfig"]
        self.assertEqual(cfg["mode"]["default"], rc.DEFAULT_MODE)
        self.assertEqual(cfg["default_tier"]["default"], rc.DEFAULT_TIER)
        self.assertEqual(cfg["explore_tier"]["default"], rc.DEFAULT_EXPLORE_TIER)


class HookWiring(unittest.TestCase):
    def setUp(self):
        self.hooks = json.loads(read("hooks", "hooks.json"))

    def test_classic_and_mod_live_in_one_file(self):
        self.assertTrue(self.hooks["description"])
        self.assertEqual(self.hooks["modules"], ["./register.ts"])
        self.assertTrue(os.path.isfile(os.path.join(PLUGIN_ROOT, "hooks", "register.ts")))

    def test_matchers_and_commands(self):
        entries = self.hooks["hooks"]["PreToolUse"]
        by_matcher = {e["matcher"]: e["hooks"] for e in entries}
        self.assertEqual(set(by_matcher), {"Agent|Task", "Workflow"})
        expected = {"Agent|Task": "agent_model.py", "Workflow": "workflow_models.py"}
        for matcher, script in expected.items():
            (hook,) = by_matcher[matcher]
            self.assertEqual(hook["type"], "command")
            self.assertEqual(hook["command"], 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/%s"' % script)
            self.assertLessEqual(hook["timeout"], 5)
            self.assertTrue(os.path.isfile(os.path.join(PLUGIN_ROOT, "hooks", script)))

    def test_no_shell_form_user_config_substitution(self):
        self.assertNotIn("user_config", read("hooks", "hooks.json"))

    def test_every_python_file_compiles(self):
        for path in glob.glob(os.path.join(PLUGIN_ROOT, "**", "*.py"), recursive=True):
            with self.subTest(path=os.path.relpath(path, PLUGIN_ROOT)):
                with tempfile.TemporaryDirectory() as tmp:
                    py_compile.compile(path, cfile=os.path.join(tmp, "x.pyc"), doraise=True)

    def test_hook_scripts_use_no_post_3_9_syntax_we_can_spot(self):
        for name in ("router_common.py", "agent_model.py", "workflow_models.py"):
            text = read("hooks", name)
            with self.subTest(name=name):
                self.assertIsNone(re.search(r"^\s*match\s+\w+.*:\s*$", text, re.M))
                self.assertIsNone(re.search(r"def \w+\([^)]*:\s*\w+\s*\|\s*\w+", text))


class SkillBudget(unittest.TestCase):
    def test_only_one_skill_and_nothing_else_always_on(self):
        self.assertEqual(sorted(os.listdir(os.path.join(PLUGIN_ROOT, "skills"))), ["router"])
        self.assertFalse(os.path.exists(os.path.join(PLUGIN_ROOT, "agents")))
        self.assertFalse(os.path.exists(os.path.join(PLUGIN_ROOT, "commands")))

    def test_skill_frontmatter_and_size(self):
        text = read("skills", "router", "SKILL.md")
        meta = frontmatter(text)
        self.assertEqual(meta["name"], "router")
        desc = meta["description"]
        self.assertLessEqual(len(desc), 250)
        self.assertTrue(desc.startswith("Use when") or desc.split()[0].lower().endswith(("e", "t", "s", "d", "y")))
        body = text.split("---", 2)[2]
        self.assertLessEqual(len(body.encode("utf-8")), 6 * 1024)

    def test_always_on_description_weight_is_under_the_budget(self):
        total = len(frontmatter(read("skills", "router", "SKILL.md"))["description"])
        self.assertLess(total, 1000)


class PublicCopy(unittest.TestCase):
    """Rules about the plugin's public wording that need no list of forbidden terms. Scanning for
    internal names and banned vocabulary is done centrally by the suite's release tooling."""

    PUBLIC = [("README.md",), ("skills", "router", "SKILL.md"), (".claude-plugin", "plugin.json")]

    def texts(self):
        return [(os.path.join(*p), read(*p)) for p in self.PUBLIC]

    def test_expensive_appears_only_inside_the_promise(self):
        for name, text in self.texts():
            with self.subTest(file=name):
                self.assertNotIn("expensive", text.replace(PROMISE, "").lower())

    def test_no_percent_signs_or_savings_numbers(self):
        for name, text in self.texts():
            with self.subTest(file=name):
                self.assertNotIn("%", text)
                self.assertIsNone(re.search(r"\b(fewer|less|cut|lower|reduce[sd]?)\b[^.\n]{0,30}\b\d", text, re.I))

    def test_no_full_model_ids_in_public_text(self):
        for name, text in self.texts():
            with self.subTest(file=name):
                self.assertIsNone(re.search(r"claude-(?:opus|sonnet|haiku)-\d", text))

    def test_only_aliases_named_as_models(self):
        text = read("README.md") + read("skills", "router", "SKILL.md")
        for alias in ("haiku", "sonnet", "opus"):
            self.assertIn(alias, text)

    def test_the_percent_and_savings_checks_can_see_a_known_positive(self):
        """Silence is only a finding if the check could have spoken."""
        bad = "It uses 40% fewer 3 things."
        self.assertIn("%", bad)
        self.assertIsNotNone(re.search(r"\b(fewer|less|cut|lower|reduce[sd]?)\b[^.\n]{0,30}\b\d", bad, re.I))


def unquoted_colon_keys(lines):
    """Frontmatter keys whose unquoted value contains ': ' (the form the suite's linter rejects)."""
    bad = []
    for line in lines:
        key, _, value = line.partition(":")
        value = value.strip()
        if value[:1] in ("'", '"'):
            continue
        if ": " in value:
            bad.append(key)
    return bad


def frontmatter_lines(text):
    lines = text.splitlines()
    assert lines[0] == "---"
    out = []
    for line in lines[1:]:
        if line == "---":
            break
        out.append(line)
    return out


class FrontmatterQuoting(unittest.TestCase):
    """The suite's linter reads frontmatter as `key: value` lines: a value holding ': ' must be quoted."""

    def test_skill_frontmatter_has_no_unquoted_colon_values(self):
        self.assertEqual(unquoted_colon_keys(frontmatter_lines(read("skills", "router", "SKILL.md"))), [])

    def test_the_check_can_see_a_known_positive(self):
        sample = ["name: x", "description: Set it on purpose: haiku or sonnet", 'other: "quoted: fine"']
        self.assertEqual(unquoted_colon_keys(sample), ["description"])


if __name__ == "__main__":
    unittest.main()
